"""DB 없이 확인 가능한 독서방 생성·초대 링크 요청 검증 테스트."""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import AppException, BadRequest, Conflict, Forbidden, NotFound
from app.core.security import create_access_token
from app.domains.book.service import BookService
from app.domains.room.models import Bookroom, BookroomMember
from app.domains.room.schemas import RoomCreateRequest
from app.domains.room.service import RoomService

AUTH = {"Authorization": f"Bearer {create_access_token(1)}"}
CHAPTERS = [{"title": "1장", "start_page": 1}, {"title": "2장", "start_page": 30}]


def room_body(**overrides) -> dict:
    body = {
        "book_id": 1,
        "title": "같이 읽어요",
        "max_capacity": 5,
        "start_date": "2026-12-01T00:00:00Z",
        "end_date": "2026-12-31T00:00:00Z",
        "is_public": True,
        "chapters": CHAPTERS,
    }
    return {**body, **overrides}


def _make_service() -> RoomService:
    """실제 DB 없이 Repository를 Mocking한 RoomService 생성."""
    db = AsyncMock()
    db.add = MagicMock()
    service = RoomService(db)
    service.repo = MagicMock()
    service.repo.get = AsyncMock()
    service.repo.get_book = AsyncMock(
        return_value=SimpleNamespace(book_id=1, status="approved", chapters=None)
    )
    service.repo.has_active_room_for_book = AsyncMock(return_value=False)
    service.repo.get_by_link = AsyncMock()
    return service


def _flush_assigns_room_id(service: RoomService, room_id: int = 10) -> None:
    """flush 시점에 DB가 room_id를 발급하는 것처럼 흉내."""

    async def flush():
        for call in service.repo.add.call_args_list:
            if isinstance(call.args[0], Bookroom):
                call.args[0].bookroom_id = room_id

    service.db.flush.side_effect = flush


def _added(service: RoomService, model: type) -> list:
    return [c.args[0] for c in service.repo.add.call_args_list if isinstance(c.args[0], model)]


# 22. 독서방 생성 (POST /api/rooms)
async def test_create_room_requires_token(client):
    res = await client.post("/api/rooms", json=room_body())
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


async def test_create_room_rejects_blank_title(client):
    res = await client.post("/api/rooms", json=room_body(title="   "), headers=AUTH)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


async def test_create_room_rejects_capacity_below_two(client):
    res = await client.post("/api/rooms", json=room_body(max_capacity=1), headers=AUTH)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


async def test_create_room_rejects_invalid_date_format(client):
    res = await client.post("/api/rooms", json=room_body(start_date="내일"), headers=AUTH)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


async def test_create_room_rejects_blank_chapter_title(client):
    chapters = [{"title": " ", "start_page": 1}, {"title": "2장", "start_page": 30}]
    res = await client.post("/api/rooms", json=room_body(chapters=chapters), headers=AUTH)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


async def test_create_room_missing_book_raises_404():
    service = _make_service()
    service.repo.get_book.return_value = SimpleNamespace(book_id=1, status="pending", chapters=None)

    with pytest.raises(NotFound) as exc_info:
        await service.create_room(member_id=1, body=RoomCreateRequest(**room_body()))

    assert exc_info.value.code == "BOOK_NOT_FOUND"


async def test_create_room_rejects_end_before_start():
    service = _make_service()
    body = RoomCreateRequest(**room_body(end_date="2026-12-01T00:00:00Z"))

    with pytest.raises(BadRequest) as exc_info:
        await service.create_room(member_id=1, body=body)

    assert exc_info.value.code == "INVALID_DATE_RANGE"


async def test_create_private_room_requires_password():
    service = _make_service()
    body = RoomCreateRequest(**room_body(is_public=False, password="  "))

    with pytest.raises(BadRequest) as exc_info:
        await service.create_room(member_id=1, body=body)

    assert exc_info.value.code == "PASSWORD_REQUIRED"


async def test_create_room_requires_two_chapters_when_book_has_none():
    service = _make_service()
    body = RoomCreateRequest(**room_body(chapters=CHAPTERS[:1]))

    with pytest.raises(BadRequest) as exc_info:
        await service.create_room(member_id=1, body=body)

    assert exc_info.value.code == "CHAPTERS_TOO_FEW"


async def test_create_room_warns_duplicate_book_room():
    service = _make_service()
    service.repo.has_active_room_for_book.return_value = True

    with pytest.raises(Conflict) as exc_info:
        await service.create_room(member_id=1, body=RoomCreateRequest(**room_body()))

    assert exc_info.value.code == "DUPLICATE_BOOK_ROOM"
    service.db.commit.assert_not_awaited()


async def test_create_room_with_confirm_skips_duplicate_check():
    service = _make_service()
    service.repo.has_active_room_for_book.return_value = True
    _flush_assigns_room_id(service)

    result = await service.create_room(
        member_id=1, body=RoomCreateRequest(**room_body(confirm_duplicate=True))
    )

    assert result.room_id == 10
    service.db.commit.assert_awaited_once()


async def test_create_room_saves_chapters_room_and_owner():
    service = _make_service()
    book = service.repo.get_book.return_value
    _flush_assigns_room_id(service)

    result = await service.create_room(
        member_id=1, body=RoomCreateRequest(**room_body(is_public=False, password="1234"))
    )

    assert [c.chapter_number for c in result.chapters] == [1, 2]
    assert json.loads(book.chapters)[1] == {"chapter_number": 2, "title": "2장", "start_page": 30}

    room = _added(service, Bookroom)[0]
    assert room.owner_id == 1
    assert room.status == "OPEN"
    assert room.password != "1234"  # 해시로 저장

    owner = _added(service, BookroomMember)[0]
    assert (owner.bookroom_id, owner.member_id, owner.member_status) == (10, 1, "active")
    service.db.commit.assert_awaited_once()


async def test_create_room_keeps_existing_chapters():
    service = _make_service()
    saved = json.dumps([{"chapter_number": 1, "title": "기존 1장", "start_page": 1}] * 2)
    service.repo.get_book.return_value = SimpleNamespace(
        book_id=1, status="approved", chapters=saved
    )
    _flush_assigns_room_id(service)

    # 요청 목차가 1개뿐이어도 책에 목차가 있으면 무시하고 통과
    result = await service.create_room(
        member_id=1, body=RoomCreateRequest(**room_body(chapters=CHAPTERS[:1]))
    )

    assert result.chapters[0].title == "기존 1장"
    assert service.repo.get_book.return_value.chapters == saved


async def test_create_room_without_start_page_saves_null():
    service = _make_service()
    book = service.repo.get_book.return_value
    _flush_assigns_room_id(service)
    chapters = [{"title": "1장"}, {"title": "2장", "start_page": None}]

    result = await service.create_room(
        member_id=1, body=RoomCreateRequest(**room_body(chapters=chapters))
    )

    assert [c.start_page for c in result.chapters] == [None, None]
    assert json.loads(book.chapters) == [
        {"chapter_number": 1, "title": "1장", "start_page": None},
        {"chapter_number": 2, "title": "2장", "start_page": None},
    ]


async def test_create_room_rejects_zero_start_page(client):
    chapters = [{"title": "1장", "start_page": 0}, {"title": "2장"}]
    res = await client.post("/api/rooms", json=room_body(chapters=chapters), headers=AUTH)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


# 103. 책 목차 조회 (GET /api/books/{book_id}/chapters)
async def test_book_chapters_empty_returns_false():
    service = BookService(AsyncMock())
    service.repo = MagicMock()
    service.repo.get = AsyncMock(
        return_value=SimpleNamespace(book_id=1, status="approved", chapters=None)
    )

    result = await service.get_chapters(1)

    assert result.has_chapters is False
    assert result.chapters == []


async def test_book_chapters_returns_null_start_page():
    saved = json.dumps(
        [
            {"chapter_number": 1, "title": "1장", "start_page": None},
            {"chapter_number": 2, "title": "2장"},  # start_page 키가 없어도 null
        ]
    )
    service = BookService(AsyncMock())
    service.repo = MagicMock()
    service.repo.get = AsyncMock(
        return_value=SimpleNamespace(book_id=1, status="approved", chapters=saved)
    )

    result = await service.get_chapters(1)

    assert result.has_chapters is True
    assert [c.model_dump() for c in result.chapters] == [
        {"chapter_number": 1, "title": "1장", "start_page": None},
        {"chapter_number": 2, "title": "2장", "start_page": None},
    ]


async def test_book_chapters_pending_book_raises_404():
    service = BookService(AsyncMock())
    service.repo = MagicMock()
    service.repo.get = AsyncMock(return_value=SimpleNamespace(book_id=1, status="pending"))

    with pytest.raises(NotFound) as exc_info:
        await service.get_chapters(1)

    assert exc_info.value.code == "BOOK_NOT_FOUND"


# 29. 초대 링크 생성 (POST /api/rooms/{room_id}/invite-link)
async def test_invite_link_requires_token(client):
    res = await client.post("/api/rooms/1/invite-link")
    assert res.status_code == 401


async def test_invite_link_owner_only():
    service = _make_service()
    service.repo.get.return_value = SimpleNamespace(bookroom_id=1, owner_id=2, status="OPEN")

    with pytest.raises(Forbidden) as exc_info:
        await service.create_invite_link(member_id=1, room_id=1)

    assert exc_info.value.code == "ROOM_OWNER_ONLY"


async def test_invite_link_replaces_code():
    service = _make_service()
    room = SimpleNamespace(bookroom_id=1, owner_id=1, status="OPEN", link="old")
    service.repo.get.return_value = room

    result = await service.create_invite_link(member_id=1, room_id=1)

    assert room.link == result.invite_code != "old"
    assert len(result.invite_code) <= 50
    assert room.link_expires_at - datetime.now(UTC) > timedelta(days=6)


# 30. 초대 링크 진입 (GET /api/invites/{invite_code})
async def test_invite_requires_token(client):
    res = await client.get("/api/invites/abc")
    assert res.status_code == 401


async def test_invite_not_found_raises_404():
    service = _make_service()
    service.repo.get_by_link.return_value = None

    with pytest.raises(NotFound) as exc_info:
        await service.get_invite(member_id=1, invite_code="abc")

    assert exc_info.value.code == "INVITE_NOT_FOUND"


async def test_expired_invite_raises_410():
    service = _make_service()
    service.repo.get_by_link.return_value = SimpleNamespace(
        bookroom_id=1, link="abc", link_expires_at=datetime.now(UTC) - timedelta(minutes=1)
    )

    with pytest.raises(AppException) as exc_info:
        await service.get_invite(member_id=1, invite_code="abc")

    assert exc_info.value.status_code == 410
    assert exc_info.value.code == "INVITE_EXPIRED"
