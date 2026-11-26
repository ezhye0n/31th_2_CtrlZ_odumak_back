"""DB 없이 확인하는 독서방 미리보기 규칙(rule) 공개 범위 테스트."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domains.room.service import RoomService

RULE = "스포 금지"


def _make_service(is_public: bool, my_status: str | None = None) -> RoomService:
    """실제 DB 없이 Repository를 Mocking한 RoomService 생성."""
    now = datetime.now(UTC)
    room = SimpleNamespace(
        bookroom_id=1,
        title="같이 읽어요",
        description="한 달 완독",
        rule=RULE,
        max_capacity=5,
        is_public=is_public,
        status="OPEN",
        start_date=now,
        end_date=now + timedelta(days=30),
        link="invite",
        link_expires_at=now + timedelta(days=1),
    )
    book = SimpleNamespace(book_id=7, title="소년이 온다", writer="한강", cover_image_url=None)

    service = RoomService(AsyncMock())
    service.repo = MagicMock()
    service.repo.get = AsyncMock(return_value=room)
    service.repo.get_with_book = AsyncMock(return_value=(room, book))
    service.repo.get_by_link = AsyncMock(return_value=room)
    service.repo.count_active_members = AsyncMock(return_value=2)
    service.repo.count_offered = AsyncMock(return_value=0)
    service.repo.list_expired_offers = AsyncMock(return_value=[])
    service.repo.get_first_waiting = AsyncMock(return_value=None)
    service.repo.get_member = AsyncMock(
        return_value=SimpleNamespace(member_status=my_status) if my_status else None
    )
    return service


# 31. 미리보기 (GET /api/rooms/{room_id})
async def test_private_room_hides_rule_for_stranger():
    service = _make_service(is_public=False)

    result = await service.get_preview(member_id=1, room_id=1)

    assert result.rule is None
    # 규칙 외 정보는 그대로
    assert (result.title, result.description, result.book_title) == (
        "같이 읽어요",
        "한 달 완독",
        "소년이 온다",
    )
    assert result.member_count == 2
    assert result.my_member_status is None


@pytest.mark.parametrize("status", ["left", "kicked"])
async def test_private_room_hides_rule_for_left_or_kicked(status):
    service = _make_service(is_public=False, my_status=status)

    result = await service.get_preview(member_id=1, room_id=1)

    assert result.rule is None
    assert result.my_member_status == status


@pytest.mark.parametrize("status", ["active", "waiting"])
async def test_private_room_shows_rule_for_active_or_waiting(status):
    service = _make_service(is_public=False, my_status=status)

    result = await service.get_preview(member_id=1, room_id=1)

    assert result.rule == RULE


async def test_public_room_shows_rule_for_stranger():
    service = _make_service(is_public=True)

    result = await service.get_preview(member_id=1, room_id=1)

    assert result.rule == RULE


# 30. 초대 링크 진입 (GET /api/invites/{invite_code})
async def test_private_room_shows_rule_via_invite():
    service = _make_service(is_public=False)

    result = await service.get_invite(member_id=1, invite_code="invite")

    assert result.rule == RULE
    assert result.room_id == 1
