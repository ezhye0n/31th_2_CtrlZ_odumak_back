import json

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequest, Conflict, NotFound
from app.domains.book.models import Booklist
from app.domains.book.repository import BookRepository
from app.domains.book.schemas import (
    BookChaptersResponse,
    BookRequestCreate,
    BookRequestResult,
    BookResponse,
    ChapterItem,
    RoomItem,
)

APPROVED = "approved"
PENDING = "pending"
SEARCH_LIMIT = 50


def load_chapters(raw: str | None) -> list[ChapterItem]:
    # booklist.chapters(JSON 문자열) -> 목차 목록, 비어 있거나 형식이 다르면 빈 목록
    if not raw:
        return []
    try:
        return [ChapterItem.model_validate(item) for item in json.loads(raw)]
    except (ValueError, TypeError, ValidationError):
        return []


def dump_chapters(chapters: list[ChapterItem]) -> str:
    # 목차 목록 -> booklist.chapters에 저장할 JSON 문자열
    return json.dumps([chapter.model_dump() for chapter in chapters], ensure_ascii=False)


class BookService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = BookRepository(db)

    async def get_book(self, book_id: int) -> BookResponse:
        ##S-07-1 책 정보 조회
        book = await self.repo.get(book_id)
        if book is None or book.status != APPROVED:
            raise NotFound("BOOK_NOT_FOUND", "요청한 책을 찾을 수 없습니다.")
        return BookResponse(
            book_id=book.book_id,
            title=book.title,
            writer=book.writer,
            isbn=book.ISBN,
            cover_image_url=book.cover_image_url,
        )

    async def search(self, keyword: str | None) -> list[BookResponse]:
        # S-05-1 책 검색 - 승인된 책만, 제목순 최대 50개
        keyword = (keyword or "").strip()
        if not keyword:
            raise BadRequest("INVALID_INPUT", "keyword 값이 누락되었거나 형식이 올바르지 않습니다.")

        books = await self.repo.search(keyword, APPROVED, SEARCH_LIMIT)
        return [
            BookResponse(
                book_id=book.book_id,
                title=book.title,
                writer=book.writer,
                isbn=book.ISBN,
                cover_image_url=book.cover_image_url,
            )
            for book in books
        ]

    async def request_book(self, member_id: int, body: BookRequestCreate) -> BookRequestResult:
        # S-06-1 도서 등록 요청 - S-06-2 중복 요청 병합

        # 승인·대기 중인 책만 비교
        same_books = await self.repo.find_same_books(
            body.title, body.writer, body.isbn, (APPROVED, PENDING)
        )

        # 409 - 이미 승인된 책 -> 검색 안내
        if any(book.status == APPROVED for book in same_books):
            raise Conflict("BOOK_ALREADY_EXISTS", "이미 등록된 책입니다. 검색해서 찾아보세요.")

        # 대기 중인 같은 요청이 있으면 새로 만들지 않고 요청 수만 +1
        pending = next((book for book in same_books if book.status == PENDING), None)
        if pending is not None:
            await self.repo.increase_request_count(pending.book_id)
            await self.db.commit()
            return BookRequestResult(request_id=pending.book_id, merged=True)

        # 처음 들어온 요청이면 pending 상태로 새로 저장
        book = Booklist(
            title=body.title,
            writer=body.writer,
            ISBN=body.isbn,
            cover_image_url=body.cover_image_url,
            status=PENDING,
            request_count=1,
            requester_id=member_id,
        )
        self.repo.add(book)
        await self.db.commit()
        await self.db.refresh(book)
        return BookRequestResult(request_id=book.book_id, merged=False)

    async def get_chapters(self, book_id: int) -> BookChaptersResponse:
        # S-10-6 책 목차 조회

        # 404 - 책이 없거나 승인 전
        book = await self.repo.get(book_id)
        if book is None or book.status != APPROVED:
            raise NotFound("BOOK_NOT_FOUND", "요청한 책을 찾을 수 없습니다.")

        chapters = load_chapters(book.chapters)
        return BookChaptersResponse(has_chapters=bool(chapters), chapters=chapters)

    async def list_rooms(self, book_id: int, sort: str, room_filter: str | None) -> list[RoomItem]:
        # S-08-1 책별 독서방 목록 - CLOSED 방 제외

        # 404 - 책이 없거나 승인 전
        await self.get_book(book_id)

        rows = await self.repo.list_rooms(book_id, sort, room_filter)
        return [
            RoomItem(
                room_id=room.bookroom_id,
                title=room.title,
                description=room.description,
                max_capacity=room.max_capacity,
                member_count=member_count,
                is_public=room.is_public,
                start_date=room.start_date,
                end_date=room.end_date,
            )
            for room, member_count in rows
        ]
