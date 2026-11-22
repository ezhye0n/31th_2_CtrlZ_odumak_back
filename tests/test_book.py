"""DB 없이 확인 가능한 책(book) 요청 검증 테스트."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import Conflict, NotFound
from app.core.security import create_access_token
from app.domains.book.models import Booklist
from app.domains.book.schemas import BookRequestCreate
from app.domains.book.service import BookService

AUTH = {"Authorization": f"Bearer {create_access_token(1)}"}


def _make_service() -> BookService:
    """실제 DB 없이 Repository를 Mocking한 BookService 생성."""
    db = AsyncMock()
    service = BookService(db)
    service.repo = MagicMock()
    service.repo.get = AsyncMock()
    service.repo.search = AsyncMock()
    service.repo.find_same_books = AsyncMock()
    service.repo.increase_request_count = AsyncMock()
    service.repo.list_rooms = AsyncMock()
    return service


def _book(book_id: int, status: str) -> SimpleNamespace:
    return SimpleNamespace(book_id=book_id, status=status)


# 15. 책 검색 (GET /api/books/search)
async def test_search_requires_keyword(client):
    res = await client.get("/api/books/search")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


async def test_search_rejects_blank_keyword(client):
    res = await client.get("/api/books/search", params={"keyword": "   "})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


# 16·17. 도서 등록 요청 (POST /api/books/requests)
async def test_request_book_requires_token(client):
    res = await client.post("/api/books/requests", json={"title": "책", "writer": "저자"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


async def test_request_book_rejects_blank_title(client):
    res = await client.post(
        "/api/books/requests", json={"title": "  ", "writer": "저자"}, headers=AUTH
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


async def test_request_book_requires_writer(client):
    res = await client.post("/api/books/requests", json={"title": "책"}, headers=AUTH)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


async def test_request_book_rejects_long_title(client):
    body = {"title": "a" * 256, "writer": "저자"}
    res = await client.post("/api/books/requests", json=body, headers=AUTH)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


async def test_request_new_book_creates_pending():
    service = _make_service()
    service.repo.find_same_books.return_value = []
    service.db.refresh.side_effect = lambda book: setattr(book, "book_id", 10)

    result = await service.request_book(
        member_id=1, body=BookRequestCreate(title="책", writer="저자", isbn="9788900000000")
    )

    assert result.request_id == 10
    assert result.merged is False
    saved: Booklist = service.repo.add.call_args.args[0]
    assert saved.status == "pending"
    assert saved.request_count == 1
    assert saved.requester_id == 1
    assert saved.ISBN == "9788900000000"
    service.db.commit.assert_awaited_once()


async def test_request_pending_book_is_merged():
    service = _make_service()
    service.repo.find_same_books.return_value = [_book(5, "pending")]

    result = await service.request_book(
        member_id=2, body=BookRequestCreate(title="책", writer="저자")
    )

    assert result.request_id == 5
    assert result.merged is True
    service.repo.increase_request_count.assert_awaited_once_with(5)
    service.repo.add.assert_not_called()


async def test_request_approved_book_raises_409():
    service = _make_service()
    service.repo.find_same_books.return_value = [_book(3, "approved")]

    with pytest.raises(Conflict) as exc_info:
        await service.request_book(member_id=1, body=BookRequestCreate(title="책", writer="저자"))

    assert exc_info.value.code == "BOOK_ALREADY_EXISTS"
    service.repo.add.assert_not_called()


async def test_request_book_ignores_rejected():
    service = _make_service()
    service.repo.find_same_books.return_value = []
    service.db.refresh.side_effect = lambda book: setattr(book, "book_id", 11)

    await service.request_book(member_id=1, body=BookRequestCreate(title="책", writer="저자"))

    # rejected는 비교 대상에서 빠져야 다시 요청할 수 있음
    statuses = service.repo.find_same_books.call_args.args[3]
    assert "rejected" not in statuses


# 21. 책별 독서방 목록 (GET /api/books/{book_id}/rooms)
async def test_list_rooms_rejects_invalid_sort(client):
    res = await client.get("/api/books/1/rooms", params={"sort": "popular"})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


async def test_list_rooms_rejects_invalid_filter(client):
    res = await client.get("/api/books/1/rooms", params={"filter": "private"})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


async def test_list_rooms_missing_book_raises_404():
    service = _make_service()
    service.repo.get.return_value = None

    with pytest.raises(NotFound) as exc_info:
        await service.list_rooms(book_id=1, sort="latest", room_filter=None)

    assert exc_info.value.code == "BOOK_NOT_FOUND"
    service.repo.list_rooms.assert_not_called()


async def test_list_rooms_pending_book_raises_404():
    service = _make_service()
    service.repo.get.return_value = SimpleNamespace(book_id=1, status="pending")

    with pytest.raises(NotFound) as exc_info:
        await service.list_rooms(book_id=1, sort="latest", room_filter=None)

    assert exc_info.value.code == "BOOK_NOT_FOUND"
