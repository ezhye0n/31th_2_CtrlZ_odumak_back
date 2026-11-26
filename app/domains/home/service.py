from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import Unauthorized
from app.domains.book.service import load_chapters
from app.domains.home.repository import HomeRepository
from app.domains.home.schemas import (
    ActiveRoomItem,
    ActiveRoomsResponse,
    RecommendationsResponse,
    RecommendedBook,
)

NEW_MEMO_WINDOW = timedelta(hours=24)
RECOMMEND_LIMIT = 10


class HomeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = HomeRepository(db)

    async def get_active_rooms(self, member_id: int, limit: int | None) -> ActiveRoomsResponse:
        # S-04-1 진행중인 독서방 - 최근 참여 순, 방마다 진행 상황과 새 메모 수
        member = await self.repo.get_member(member_id)
        if member is None:
            raise Unauthorized()

        since = datetime.now(UTC) - NEW_MEMO_WINDOW
        rows = await self.repo.list_active_rooms(member_id, since, limit)
        rooms = [
            ActiveRoomItem(
                room_id=room.bookroom_id,
                title=room.title,
                book_title=book.title,
                book_writer=book.writer,
                cover_image_url=book.cover_image_url,
                current_chapter=room_member.current_chapter,
                current_chapter_title=_chapter_title(book.chapters, room_member.current_chapter),
                page=room_member.page,
                progress_rate=room_member.progress_rate,
                member_count=member_count,
                reading_status=room_member.status,
                new_memo_count=new_memo_count,
            )
            for room_member, room, book, member_count, new_memo_count in rows
        ]
        member_name = _display_name(member.name, member.email)
        return ActiveRoomsResponse(member_name=member_name, rooms=rooms)

    async def get_recommendations(self, member_id: int) -> RecommendationsResponse:
        # S-04-2 추천 도서 - 참여자 많은 책 순, 내가 읽는 중인 책 제외, 최대 10권
        books = await self.repo.list_recommended_books(member_id, RECOMMEND_LIMIT)
        return RecommendationsResponse(
            books=[
                RecommendedBook(
                    book_id=book.book_id,
                    title=book.title,
                    writer=book.writer,
                    cover_image_url=book.cover_image_url,
                )
                for book in books
            ]
        )


def _display_name(name: str | None, email: str) -> str:
    # 이름이 비어 있으면 이메일 @ 앞부분
    if name and name.strip():
        return name
    return email.split("@")[0]


def _chapter_title(raw_chapters: str | None, chapter_number: int) -> str | None:
    # 책 목차에서 현재 챕터 번호의 제목 찾기, 없으면 None
    for chapter in load_chapters(raw_chapters):
        if chapter.chapter_number == chapter_number:
            return chapter.title
    return None
