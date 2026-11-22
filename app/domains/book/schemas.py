from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints


class BookResponse(BaseModel):
    book_id: int
    title: str
    writer: str
    isbn: str | None
    cover_image_url: str | None


# 공백 제거 후 1자 이상, 최대 길이는 booklist 컬럼 길이와 맞춤 (위반 시 400 INVALID_INPUT)
BookTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
BookWriter = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
BookIsbn = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
CoverImageUrl = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]


class BookRequestCreate(BaseModel):
    title: BookTitle
    writer: BookWriter
    isbn: BookIsbn | None = None
    cover_image_url: CoverImageUrl | None = None


class BookRequestResult(BaseModel):
    request_id: int  # 요청이 저장된 booklist.book_id
    merged: bool  # 기존 pending 요청 병합 : true


class ChapterItem(BaseModel):
    chapter_number: int  # 1부터
    title: str
    start_page: int


class BookChaptersResponse(BaseModel):
    has_chapters: bool
    chapters: list[ChapterItem]


class RoomItem(BaseModel):
    room_id: int
    title: str
    description: str | None
    max_capacity: int
    member_count: int
    is_public: bool
    start_date: datetime
    end_date: datetime
