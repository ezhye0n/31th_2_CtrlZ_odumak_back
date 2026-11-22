from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class RoomHomeInfo(BaseModel):
    bookroom_id: int
    title: str
    book_title: str


class RoomHomeResponse(BaseModel):
    room: RoomHomeInfo
    role: Literal["owner", "member"]


class RoomRulesResponse(BaseModel):
    rule: str
    start_date: str
    end_date: str
    editable: bool


class MemberCompleteRequest(BaseModel):
    action: Literal["stay", "leave"]


class MemberProgressUpdateRequest(BaseModel):
    chapter: int = Field(ge=0)
    page: int | None = Field(default=None, ge=0)
    progress_rate: float = Field(ge=0, le=100)


class RoomUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    max_capacity: int | None = Field(default=None, ge=1)
    start_date: date | None = None
    end_date: date | None = None
    rule: str | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "RoomUpdateRequest":
        if self.start_date is not None and self.end_date is not None:
            if self.start_date > self.end_date:
                raise ValueError("종료일은 시작일보다 빠를 수 없습니다.")
        return self


class RoomMemberItem(BaseModel):
    member_id: int
    name: str | None = None
    role: Literal["owner", "member"]
    current_chapter: int
    page: int | None = None
    progress_rate: float


class RoomMembersResponse(BaseModel):
    members: list[RoomMemberItem]


class MemberKickRequest(BaseModel):
    reason: str | None = None


class RoomClosePreviewRequest(BaseModel):
    room_name_confirm: str


class RoomClosePreviewResponse(BaseModel):
    matched: bool


class RoomOwnerDelegateRequest(BaseModel):
    target_member_id: int


class MemberStatusUpdateRequest(BaseModel):
    status: Literal["reading", "paused", "completed"]


class MemberStatusUpdateResponse(BaseModel):
    next_step: str | None = None
