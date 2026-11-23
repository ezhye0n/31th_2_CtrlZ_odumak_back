"""DB 없이 확인하는 강퇴·퇴장·정원 변경 후 상태 변경과 대기자 이월 테스트."""

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import BadRequest, Conflict, NotFound
from app.domains.room.models import BookroomMember
from app.domains.room.schemas import RoomJoinRequest, RoomUpdateRequest
from app.domains.room.service import RoomService

OWNER_ID = 1


def _make_service(max_capacity: int = 3) -> RoomService:
    """실제 DB 없이 Repository를 Mocking한 RoomService 생성."""
    service = RoomService(AsyncMock())
    service.repo = MagicMock()
    service.repo.get = AsyncMock(
        return_value=SimpleNamespace(
            bookroom_id=1, owner_id=OWNER_ID, title="방", max_capacity=max_capacity
        )
    )
    service.repo.get_member = AsyncMock()
    service.repo.count_members = AsyncMock(return_value=2)
    service.repo.delete_member = AsyncMock()
    service.offer_next_waiting = AsyncMock(return_value=None)
    return service


def _member(member_id: int, status: str = "active") -> BookroomMember:
    return BookroomMember(
        bookroom_id=1,
        member_id=member_id,
        member_status=status,
        current_chapter=3,
        page=120,
        progress_rate=45.0,
        joined_at=datetime.now(UTC),
        offer_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


# 강퇴 (DELETE /api/rooms/{room_id}/members/{member_id})
async def test_kick_marks_member_kicked_and_offers_seat():
    service = _make_service()
    target = _member(2)
    service.repo.get_member.return_value = target

    await service.kick_member(owner_member_id=OWNER_ID, room_id=1, target_member_id=2)

    assert target.member_status == "kicked"
    assert target.offer_expires_at is None
    service.repo.delete_member.assert_not_called()
    service.db.commit.assert_awaited_once()
    service.offer_next_waiting.assert_awaited_once_with(1)


@pytest.mark.parametrize("status", ["waiting", "left", "kicked"])
async def test_kick_non_active_member_raises_404(status):
    service = _make_service()
    service.repo.get_member.return_value = _member(2, status)

    with pytest.raises(NotFound) as exc_info:
        await service.kick_member(owner_member_id=OWNER_ID, room_id=1, target_member_id=2)

    assert exc_info.value.code == "MEMBER_NOT_FOUND"
    service.offer_next_waiting.assert_not_called()


async def test_owner_cannot_kick_self():
    service = _make_service()

    with pytest.raises(BadRequest) as exc_info:
        await service.kick_member(owner_member_id=OWNER_ID, room_id=1, target_member_id=OWNER_ID)

    assert exc_info.value.code == "CANNOT_KICK_OWNER"


# 퇴장 (POST /api/rooms/{room_id}/members/me/complete, action=leave)
async def test_leave_marks_member_left_and_keeps_progress():
    service = _make_service()
    member = _member(2)
    service.repo.get_member.return_value = member

    await service.complete_member(member_id=2, room_id=1, action="leave")

    assert member.member_status == "left"
    # 다시 참여하면 이어서 읽을 수 있도록 진행도 유지
    assert (member.current_chapter, member.page, member.progress_rate) == (3, 120, 45.0)
    service.repo.delete_member.assert_not_called()
    service.db.commit.assert_awaited_once()
    service.offer_next_waiting.assert_awaited_once_with(1)


async def test_owner_must_delegate_before_leave():
    service = _make_service()
    service.repo.get_member.return_value = _member(OWNER_ID)

    with pytest.raises(Conflict) as exc_info:
        await service.complete_member(member_id=OWNER_ID, room_id=1, action="leave")

    assert exc_info.value.code == "OWNER_MUST_DELEGATE"
    service.offer_next_waiting.assert_not_called()


async def test_stay_keeps_member_active():
    service = _make_service()
    member = _member(2)
    service.repo.get_member.return_value = member

    await service.complete_member(member_id=2, room_id=1, action="stay")

    assert member.member_status == "active"
    service.offer_next_waiting.assert_not_called()


# 정원 변경 (PATCH /api/rooms/{room_id})
async def test_capacity_increase_offers_seat():
    service = _make_service(max_capacity=3)

    await service.update_room(member_id=OWNER_ID, room_id=1, body=RoomUpdateRequest(max_capacity=5))

    assert service.repo.get.return_value.max_capacity == 5
    service.db.commit.assert_awaited_once()
    service.offer_next_waiting.assert_awaited_once_with(1)


@pytest.mark.parametrize("body", [{"max_capacity": 3}, {"max_capacity": 2}, {"title": "새 제목"}])
async def test_update_without_capacity_increase_does_not_offer(body):
    service = _make_service(max_capacity=3)

    await service.update_room(member_id=OWNER_ID, room_id=1, body=RoomUpdateRequest(**body))

    service.db.commit.assert_awaited_once()
    service.offer_next_waiting.assert_not_called()


async def test_capacity_below_members_still_rejected():
    service = _make_service(max_capacity=3)
    service.repo.count_members.return_value = 3

    with pytest.raises(Conflict) as exc_info:
        await service.update_room(
            member_id=OWNER_ID,
            room_id=1,
            body=RoomUpdateRequest(max_capacity=2, start_date=date(2026, 12, 1)),
        )

    assert exc_info.value.code == "CAPACITY_BELOW_MEMBERS"
    service.offer_next_waiting.assert_not_called()


# 퇴장 후 재참여 (POST /api/rooms/{room_id}/join)
# 강퇴자 join·waitlist 거부(KICKED_FROM_ROOM)는 tests/test_room_join.py에 있음
async def test_left_member_rejoins_with_progress_kept():
    service = _make_service()
    service.repo.get.return_value = SimpleNamespace(
        bookroom_id=1, owner_id=OWNER_ID, status="OPEN", is_public=True, max_capacity=3
    )
    service.repo.lock_room = AsyncMock(return_value=service.repo.get.return_value)
    service.repo.list_expired_offers = AsyncMock(return_value=[])
    service.repo.count_active_members = AsyncMock(return_value=1)
    service.repo.count_offered = AsyncMock(return_value=0)
    member = _member(2, "left")
    member.offer_expires_at = None
    service.repo.get_member.return_value = member

    result = await service.join_room(member_id=2, room_id=1, body=RoomJoinRequest())

    assert result.member_status == "active"
    assert member.member_status == "active"
    assert (member.current_chapter, member.page, member.progress_rate) == (3, 120, 45.0)
    service.repo.add.assert_not_called()
    service.db.commit.assert_awaited_once()
