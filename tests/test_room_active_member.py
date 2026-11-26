"""DB 없이 확인하는 독서방 참여자(active) 판정 테스트."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from app.common.exceptions import BadRequest, Forbidden
from app.domains.room.models import BookroomMember
from app.domains.room.repository import RoomRepository
from app.domains.room.service import RoomService


def _make_service() -> RoomService:
    """실제 DB 없이 Repository를 Mocking한 RoomService 생성."""
    service = RoomService(AsyncMock())
    service.repo = MagicMock()
    service.repo.get = AsyncMock(
        return_value=SimpleNamespace(bookroom_id=1, owner_id=1, title="테스트 방", rule=None)
    )
    service.repo.get_member = AsyncMock()
    return service


def _member(member_id: int, status: str) -> BookroomMember:
    return BookroomMember(
        bookroom_id=1,
        member_id=member_id,
        member_status=status,
        joined_at=datetime.now(UTC),
        current_chapter=0,
        progress_rate=0,
    )


def _sql(stmt) -> str:
    """실행된 쿼리를 값이 들어간 SQL 문자열로 변환."""
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


# _check_room_member: active가 아니면 참여자가 아님
@pytest.mark.parametrize("status", ["waiting", "left", "kicked"])
async def test_non_active_member_is_not_room_member(status):
    service = _make_service()
    service.repo.get_member.return_value = _member(2, status)

    with pytest.raises(Forbidden) as exc_info:
        await service._check_room_member(member_id=2, room_id=1)

    assert exc_info.value.code == "NOT_ROOM_MEMBER"


async def test_active_member_passes_room_member_check():
    service = _make_service()
    member = _member(2, "active")
    service.repo.get_member.return_value = member

    _, room_member = await service._check_room_member(member_id=2, room_id=1)

    assert room_member is member


async def test_waiting_member_cannot_open_room_rules():
    service = _make_service()
    service.repo.get_member.return_value = _member(2, "waiting")

    with pytest.raises(Forbidden) as exc_info:
        await service.get_rules(member_id=2, room_id=1)

    assert exc_info.value.code == "NOT_ROOM_MEMBER"


# delegate_owner: 위임 대상도 active여야 함
@pytest.mark.parametrize("status", ["waiting", "left", "kicked"])
async def test_delegate_to_non_active_member_raises_400(status):
    service = _make_service()
    service.repo.get_member.return_value = _member(2, status)

    with pytest.raises(BadRequest) as exc_info:
        await service.delegate_owner(owner_member_id=1, room_id=1, target_member_id=2)

    assert exc_info.value.code == "INVALID_DELEGATE_TARGET"
    service.db.commit.assert_not_awaited()


async def test_delegate_to_active_member_changes_owner():
    service = _make_service()
    service.repo.get_member.return_value = _member(2, "active")

    await service.delegate_owner(owner_member_id=1, room_id=1, target_member_id=2)

    assert service.repo.get.return_value.owner_id == 2
    service.db.commit.assert_awaited_once()


# count_members, list_members_with_name: active 행만 대상
async def test_count_members_counts_only_active():
    db = AsyncMock()
    db.scalar.return_value = 3
    repo = RoomRepository(db)

    assert await repo.count_members(1) == 3

    sql = _sql(db.scalar.call_args.args[0])
    assert "bookroom_member.bookroom_id = 1" in sql
    assert "bookroom_member.member_status = 'active'" in sql


async def test_list_members_with_name_selects_only_active():
    db = AsyncMock()
    db.execute.return_value = MagicMock(all=MagicMock(return_value=[]))
    repo = RoomRepository(db)

    assert await repo.list_members_with_name(1) == []

    sql = _sql(db.execute.call_args.args[0])
    assert "bookroom_member.bookroom_id = 1" in sql
    assert "bookroom_member.member_status = 'active'" in sql
