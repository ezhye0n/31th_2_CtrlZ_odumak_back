from pydantic import BaseModel


class ActiveRoomItem(BaseModel):
    room_id: int
    title: str
    book_title: str
    book_writer: str
    cover_image_url: str | None
    current_chapter: int
    current_chapter_title: str | None  # 목차에 없으면 null
    page: int | None
    progress_rate: float
    member_count: int  # active 참여자 수
    reading_status: str  # reading / paused / completed
    new_memo_count: int  # 최근 24시간 동안 다른 사람이 쓴 메모 수


class ActiveRoomsResponse(BaseModel):
    member_name: str
    rooms: list[ActiveRoomItem]


class RecommendedBook(BaseModel):
    book_id: int
    title: str
    writer: str
    cover_image_url: str | None


class RecommendationsResponse(BaseModel):
    books: list[RecommendedBook]
