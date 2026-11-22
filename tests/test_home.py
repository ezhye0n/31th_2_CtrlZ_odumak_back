"""DB 없이 확인 가능한 홈(home) 요청 검증·응답 조합 테스트."""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import Unauthorized
from app.core.security import create_access_token
from app.domains.home.service import HomeService

AUTH = {"Authorization": f"Bearer {create_access_token(1)}"}
CHAPTERS = json.dumps(
    [
        {"chapter_number": 1, "title": "1장 시작", "start_page": 1},
        {"chapter_number": 2, "title": "2장 전개", "start_page": 40},
    ],
    ensure_ascii=False,
)


def _make_service() -> HomeService:
    """실제 DB 없이 Repository를 Mocking한 HomeService 생성."""
    service = HomeService(AsyncMock())
    service.repo = MagicMock()
    service.repo.get_member = AsyncMock(
        return_value=SimpleNamespace(member_id=1, name="독서왕", email="reader@example.com")
    )
    service.repo.list_active_rooms = AsyncMock(return_value=[])
    service.repo.list_recommended_books = AsyncMock(return_value=[])
    return service


def _row(chapter: int, chapters: str | None = CHAPTERS):
    room_member = SimpleNamespace(
        current_chapter=chapter, page=55, progress_rate=42.5, status="reading"
    )
    room = SimpleNamespace(bookroom_id=3, title="같이 읽어요")
    book = SimpleNamespace(
        book_id=7, title="소년이 온다", writer="한강", cover_image_url=None, chapters=chapters
    )
    return room_member, room, book, 4, 2


# 13. 진행중인 독서방 (GET /api/home/active-rooms)
async def test_active_rooms_requires_token(client):
    res = await client.get("/api/home/active-rooms")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.parametrize("limit", [0, 51, "many"])
async def test_active_rooms_rejects_invalid_limit(client, limit):
    res = await client.get("/api/home/active-rooms", params={"limit": limit}, headers=AUTH)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


async def test_active_rooms_builds_room_items():
    service = _make_service()
    service.repo.list_active_rooms.return_value = [_row(chapter=2)]

    result = await service.get_active_rooms(member_id=1, limit=5)

    assert result.member_name == "독서왕"
    room = result.rooms[0].model_dump()
    assert room == {
        "room_id": 3,
        "title": "같이 읽어요",
        "book_title": "소년이 온다",
        "book_writer": "한강",
        "cover_image_url": None,
        "current_chapter": 2,
        "current_chapter_title": "2장 전개",
        "page": 55,
        "progress_rate": 42.5,
        "member_count": 4,
        "reading_status": "reading",
        "new_memo_count": 2,
    }
    # 최근 24시간 기준 시각과 limit을 그대로 전달
    _, since, limit = service.repo.list_active_rooms.call_args.args
    elapsed = datetime.now(UTC) - since
    assert timedelta(hours=23, minutes=59) < elapsed <= timedelta(hours=24, seconds=5)
    assert limit == 5


@pytest.mark.parametrize(("chapter", "chapters"), [(0, CHAPTERS), (9, CHAPTERS), (1, None)])
async def test_active_rooms_chapter_title_is_null_when_missing(chapter, chapters):
    service = _make_service()
    service.repo.list_active_rooms.return_value = [_row(chapter=chapter, chapters=chapters)]

    result = await service.get_active_rooms(member_id=1, limit=None)

    assert result.rooms[0].current_chapter_title is None


@pytest.mark.parametrize("name", [None, "", "  "])
async def test_member_name_falls_back_to_email_prefix(name):
    service = _make_service()
    service.repo.get_member.return_value = SimpleNamespace(
        member_id=1, name=name, email="reader@example.com"
    )

    result = await service.get_active_rooms(member_id=1, limit=None)

    assert result.member_name == "reader"
    assert result.rooms == []


async def test_active_rooms_missing_member_raises_401():
    service = _make_service()
    service.repo.get_member.return_value = None

    with pytest.raises(Unauthorized):
        await service.get_active_rooms(member_id=1, limit=None)


# 14. 추천 (GET /api/home/recommendations)
async def test_recommendations_requires_token(client):
    res = await client.get("/api/home/recommendations")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


async def test_recommendations_builds_book_items():
    service = _make_service()
    service.repo.list_recommended_books.return_value = [
        SimpleNamespace(
            book_id=7, title="소년이 온다", writer="한강", cover_image_url="https://img", status="x"
        )
    ]

    result = await service.get_recommendations(member_id=1)

    assert [b.model_dump() for b in result.books] == [
        {"book_id": 7, "title": "소년이 온다", "writer": "한강", "cover_image_url": "https://img"}
    ]
    service.repo.list_recommended_books.assert_awaited_once_with(1, 10)
