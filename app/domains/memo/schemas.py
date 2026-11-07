from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

# 빈 본문(공백만 있는 경우 포함) 방지, 최대 500자
Content = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Quote = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class MemoCreate(BaseModel):
    chapter: int = Field(ge=1)
    quote: Quote | None = None
    content: Content
    page: int | None = Field(default=None, ge=1)
    total_pages: int | None = Field(default=None, ge=1)
    is_spoiler: bool = False

    @model_validator(mode="after")
    def check_page(self):
        if (self.page is None) != (self.total_pages is None):
            raise ValueError("page와 total_pages는 함께 전달해야 합니다.")
        if self.page is not None and self.page > self.total_pages:
            raise ValueError("page는 total_pages 이하여야 합니다.")
        return self


class MemoUpdate(BaseModel):
    content: Content | None = None
    is_spoiler: bool | None = None

    @model_validator(mode="after")
    def check_not_empty(self):
        values = self.model_dump(exclude_unset=True)
        if not values or any(v is None for v in values.values()):
            raise ValueError("content 또는 is_spoiler 중 하나 이상을 전달해야 합니다.")
        return self


class MemoItem(BaseModel):
    """목록·클러스터 열람에서 쓰는 메모 한 건."""

    model_config = ConfigDict(from_attributes=True)

    memo_id: int
    member_id: int
    chapter: int
    page: int | None
    total_pages: int | None
    quote: str | None
    content: str
    is_spoiler: bool
    is_hidden: bool
    cluster_id: int | None
    created_at: datetime
