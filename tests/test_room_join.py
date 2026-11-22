"""DB 없이 확인 가능한 독서방 참여·비밀번호·대기열 요청 검증 테스트."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import AppException, BadRequest, Conflict, Forbidden
from app.core.security import create_access_token, hash_password
from app.domains.notification.models import Notification
from app.domains.room import service as room_service
from app.domains.room.models import BookroomMember
from app.domains.room.schemas import RoomJoinRequest
from app.domains.room.service import RoomService

AUTH = {"Authorization": f"Bearer {create_access_token(1)}"}
PASSWORD_HASH = hash_password("1234")


@pytest.fixture(autouse=True)
def reset_password_failures():
    room_service._password_failures.clear()
    yield
    room_service._password_failures.clear()


def _room(**overrides) -> SimpleNamespace:
    room = {
        "bookroom_id": 1,
        "owner_id": 9,
        "status": "OPEN",
        "is_public": True,
        "password": None,
        "max_capacity": 3,
        "link": None,
        "link_expires_at": None,
    }
    return SimpleNamespace(**{**room, **overrides})


def _make_service(room: SimpleNamespace | None = None, active: int = 1, offered: int = 0):
    """실제 DB 없이 Repository를 Mocking한 RoomService 생성."""
    room = room or _room()
    service = RoomService(AsyncMock())
    service.repo = MagicMock()
    service.repo.get = AsyncMock(return_value=room)
    service.repo.lock_room = AsyncMock(return_value=room)
    service.repo.get_member = AsyncMock(return_value=None)
    service.repo.count_active_members = AsyncMock(return_value=active)
    service.repo.count_offered = AsyncMock(return_value=offered)
    service.repo.list_expired_offers = AsyncMock(return_value=[])
    service.repo.get_first_waiting = AsyncMock(return_value=None)
    service.repo.count_waiting_until = AsyncMock(return_value=1)
    return service


def _member(status: str, offer_expires_at: datetime | None = None) -> BookroomMember:
    return BookroomMember(
        bookroom_id=1,
        member_id=1,
        member_status=status,
        joined_at=datetime.now(UTC) - timedelta(days=1),
        offer_expires_at=offer_expires_at,
    )


# 31. 미리보기·참여 (GET /api/rooms/{room_id}, POST /api/rooms/{room_id}/join)
@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("GET", "/api/rooms/1"),
        ("POST", "/api/rooms/1/join"),
        ("POST", "/api/rooms/1/waitlist"),
        ("DELETE", "/api/rooms/1/waitlist"),
    ],
)
async def test_join_endpoints_require_token(client, method, url):
    res = await client.request(method, url)
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


async def test_join_closed_room_raises_409():
    service = _make_service(_room(status="CLOSED"))

    with pytest.raises(Conflict) as exc_info:
        await service.join_room(member_id=1, room_id=1, body=RoomJoinRequest())

    assert exc_info.value.code == "ROOM_CLOSED"


async def test_kicked_member_cannot_join():
    service = _make_service()
    service.repo.get_member.return_value = _member("kicked")

    with pytest.raises(Forbidden) as exc_info:
        await service.join_room(member_id=1, room_id=1, body=RoomJoinRequest())

    assert exc_info.value.code == "KICKED_FROM_ROOM"


async def test_active_member_cannot_join_again():
    service = _make_service()
    service.repo.get_member.return_value = _member("active")

    with pytest.raises(Conflict) as exc_info:
        await service.join_room(member_id=1, room_id=1, body=RoomJoinRequest())

    assert exc_info.value.code == "ALREADY_JOINED"


async def test_join_full_room_raises_409():
    # active 2명 + 우선참여권 대기자 1명 = 정원 3명
    service = _make_service(active=2, offered=1)

    with pytest.raises(Conflict) as exc_info:
        await service.join_room(member_id=1, room_id=1, body=RoomJoinRequest())

    assert exc_info.value.code == "ROOM_FULL"


async def test_offer_holder_joins_full_room():
    service = _make_service(active=2, offered=1)
    member = _member("waiting", offer_expires_at=datetime.now(UTC) + timedelta(hours=1))
    service.repo.get_member.return_value = member

    result = await service.join_room(member_id=1, room_id=1, body=RoomJoinRequest())

    assert result.member_status == "active"
    assert member.member_status == "active"
    assert member.offer_expires_at is None


async def test_left_member_rejoins_with_same_row():
    service = _make_service()
    member = _member("left")
    service.repo.get_member.return_value = member

    await service.join_room(member_id=1, room_id=1, body=RoomJoinRequest())

    assert member.member_status == "active"
    service.repo.add.assert_not_called()


async def test_new_member_joins_public_room():
    service = _make_service()

    result = await service.join_room(member_id=1, room_id=1, body=RoomJoinRequest())

    assert (result.room_id, result.member_status) == (1, "active")
    added = service.repo.add.call_args.args[0]
    assert (added.member_id, added.member_status) == (1, "active")
    service.db.commit.assert_awaited()


async def test_private_room_passes_with_valid_invite_code():
    room = _room(
        is_public=False,
        password=PASSWORD_HASH,
        link="invite",
        link_expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    service = _make_service(room)

    result = await service.join_room(
        member_id=1, room_id=1, body=RoomJoinRequest(invite_code="invite")
    )

    assert result.member_status == "active"


async def test_private_room_with_expired_invite_checks_password():
    room = _room(
        is_public=False,
        password=PASSWORD_HASH,
        link="invite",
        link_expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    service = _make_service(room)

    with pytest.raises(BadRequest) as exc_info:
        await service.join_room(
            member_id=1, room_id=1, body=RoomJoinRequest(invite_code="invite", password="0000")
        )

    assert exc_info.value.code == "WRONG_PASSWORD"


# 32·33. 비밀번호 확인 (POST /api/rooms/{room_id}/verify-password)
async def test_verify_password_requires_password(client):
    res = await client.post("/api/rooms/1/verify-password", json={}, headers=AUTH)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


async def test_verify_password_success():
    service = _make_service(_room(is_public=False, password=PASSWORD_HASH))

    result = await service.verify_room_password(member_id=1, room_id=1, password="1234")

    assert result.verified is True


async def test_wrong_password_shows_remaining_then_locks():
    service = _make_service(_room(is_public=False, password=PASSWORD_HASH))

    for remaining in [4, 3, 2, 1]:
        with pytest.raises(BadRequest) as exc_info:
            await service.verify_room_password(member_id=1, room_id=1, password="0000")
        assert exc_info.value.code == "WRONG_PASSWORD"
        assert f"남은 횟수 {remaining}회" in exc_info.value.message

    # 5번째 실패에서 잠금, 잠금 중에는 맞는 비밀번호도 거부
    for password in ["0000", "1234"]:
        with pytest.raises(AppException) as exc_info:
            await service.verify_room_password(member_id=1, room_id=1, password=password)
        assert exc_info.value.status_code == 423
        assert exc_info.value.code == "PASSWORD_LOCKED"


async def test_password_lock_expires_after_one_minute():
    service = _make_service(_room(is_public=False, password=PASSWORD_HASH))
    room_service._password_failures[(1, 1)] = (5, datetime.now(UTC) - timedelta(seconds=1))

    result = await service.verify_room_password(member_id=1, room_id=1, password="1234")

    assert result.verified is True
    assert (1, 1) not in room_service._password_failures


async def test_success_resets_failure_count():
    service = _make_service(_room(is_public=False, password=PASSWORD_HASH))
    with pytest.raises(BadRequest):
        await service.verify_room_password(member_id=1, room_id=1, password="0000")

    await service.verify_room_password(member_id=1, room_id=1, password="1234")

    with pytest.raises(BadRequest) as exc_info:
        await service.verify_room_password(member_id=1, room_id=1, password="0000")
    assert "남은 횟수 4회" in exc_info.value.message


# 26. 대기열 (POST·DELETE /api/rooms/{room_id}/waitlist)
async def test_waitlist_rejects_when_room_not_full():
    service = _make_service(active=1)

    with pytest.raises(Conflict) as exc_info:
        await service.join_waitlist(member_id=1, room_id=1)

    assert exc_info.value.code == "ROOM_NOT_FULL"


async def test_waitlist_rejects_kicked_member():
    service = _make_service(active=3)
    service.repo.get_member.return_value = _member("kicked")

    with pytest.raises(Forbidden) as exc_info:
        await service.join_waitlist(member_id=1, room_id=1)

    assert exc_info.value.code == "KICKED_FROM_ROOM"


async def test_waitlist_rejects_already_waiting():
    service = _make_service(active=3)
    service.repo.get_member.return_value = _member("waiting")

    with pytest.raises(Conflict) as exc_info:
        await service.join_waitlist(member_id=1, room_id=1)

    assert exc_info.value.code == "ALREADY_WAITING"


async def test_waitlist_returns_position():
    service = _make_service(active=3)
    service.repo.count_waiting_until.return_value = 3

    result = await service.join_waitlist(member_id=1, room_id=1)

    assert result.waiting_position == 3
    added = service.repo.add.call_args.args[0]
    assert added.member_status == "waiting"


async def test_cancel_waitlist_passes_offer_to_next():
    service = _make_service(active=2)
    member = _member("waiting", offer_expires_at=datetime.now(UTC) + timedelta(hours=1))
    service.repo.get_member.return_value = member
    next_member = _member("waiting")
    next_member.member_id = 2
    service.repo.get_first_waiting.return_value = next_member

    await service.cancel_waitlist(member_id=1, room_id=1)

    assert member.member_status == "left"
    assert next_member.offer_expires_at is not None


# 27·28. 우선참여권
async def test_offer_next_waiting_gives_24h_offer_and_notification():
    service = _make_service(active=2)
    waiting = _member("waiting")
    waiting.member_id = 5
    service.repo.get_first_waiting.return_value = waiting

    offered_id = await service.offer_next_waiting(room_id=1)

    assert offered_id == 5
    remaining = waiting.offer_expires_at - datetime.now(UTC)
    assert timedelta(hours=23) < remaining <= timedelta(hours=24)
    notification = service.repo.add.call_args.args[0]
    assert isinstance(notification, Notification)
    assert (notification.member_id, notification.type) == (5, "ROOM_SEAT_OFFERED")
    assert notification.deeplink == "/rooms/1"


async def test_offer_next_waiting_skips_when_offer_exists():
    service = _make_service(active=2, offered=1)

    assert await service.offer_next_waiting(room_id=1) is None
    service.repo.get_first_waiting.assert_not_called()


async def test_offer_next_waiting_skips_when_full():
    service = _make_service(active=3)

    assert await service.offer_next_waiting(room_id=1) is None
    service.repo.get_first_waiting.assert_not_called()


async def test_expired_offer_is_released_on_join():
    service = _make_service(active=2)
    expired = _member("waiting", offer_expires_at=datetime.now(UTC) - timedelta(minutes=1))
    expired.member_id = 7
    service.repo.list_expired_offers.return_value = [expired]

    await service.join_room(member_id=1, room_id=1, body=RoomJoinRequest())

    assert expired.member_status == "left"
    assert expired.offer_expires_at is None
