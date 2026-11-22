from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import get_current_member_id
from app.common.response import ok
from app.core.database import get_db
from app.domains.book.schemas import BookRequestCreate
from app.domains.book.service import BookService

router = APIRouter(prefix="/books", tags=["검색·탐색"])


def get_service(db: AsyncSession = Depends(get_db)) -> BookService:
    return BookService(db)


# 고정 주소 /search, /requests 같은 고정 주소는 /{book_id}보다 위
@router.get("/search")
async def search_books(
    keyword: str | None = Query(None),
    service: BookService = Depends(get_service),
):
    # S-05-1 책 검색
    books = await service.search(keyword)
    return ok({"books": [book.model_dump() for book in books]})


@router.post("/requests", status_code=status.HTTP_201_CREATED)
async def request_book(
    body: BookRequestCreate,
    member_id: int = Depends(get_current_member_id),
    service: BookService = Depends(get_service),
):
    # S-06-1 도서 등록 요청 - S-06-2 중복 요청 병합
    result = await service.request_book(member_id, body)
    return ok(result.model_dump())


@router.get("/{book_id}")
async def get_book(book_id: int, service: BookService = Depends(get_service)):
    # S-07-1 책 정보 및 방 목록 진입
    result = await service.get_book(book_id)
    return ok({"book": result.model_dump()})


@router.get("/{book_id}/rooms")
async def list_book_rooms(
    book_id: int,
    sort: Literal["latest", "deadline"] = Query("latest"),
    room_filter: Literal["public", "available"] | None = Query(None, alias="filter"),
    service: BookService = Depends(get_service),
):
    # S-08-1 책별 독서방 목록
    rooms = await service.list_rooms(book_id, sort, room_filter)
    return ok({"rooms": [room.model_dump(mode="json") for room in rooms]})


@router.get("/{book_id}/chapters")
async def get_book_chapters(book_id: int, service: BookService = Depends(get_service)):
    # S-10-6 책 목차 조회
    result = await service.get_chapters(book_id)
    return ok(result.model_dump())
