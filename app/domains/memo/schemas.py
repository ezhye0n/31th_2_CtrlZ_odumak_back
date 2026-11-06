from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MemoCreate(BaseModel):
    room_id: int
    chapter: int | None = None
    page: int | None = Field(default=None, ge=1)
    total_pages: int | None = Field(default=None, ge=1)
    quote: str | None = Field(default=None, max_length=500)
    content: str = Field(min_length=1, max_length=2000)
    is_spoiler: bool = False

    @model_validator(mode="after")
    def check_page(self):
        if self.page and self.total_pages and self.page > self.total_pages:
            raise ValueError("page는 total_pages보다 클 수 없습니다.")
        return self


class MemoUpdate(BaseModel):
    quote: str | None = Field(default=None, max_length=500)
    content: str | None = Field(default=None, min_length=1, max_length=2000)
    is_spoiler: bool | None = None


class MemoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    room_id: int
    chapter: int | None
    page: int | None
    total_pages: int | None
    quote: str | None
    content: str
    is_spoiler: bool
    cluster_id: int | None
    created_at: datetime
