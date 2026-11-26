from datetime import UTC, date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from app.domains.book.schemas import ChapterItem


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


# ---- 방 생성·참여·대기열 (22~33) ----

# 공백 제거 후 1~100자 (위반 시 400 INVALID_INPUT)
RoomTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
ChapterTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
# bcrypt는 72바이트까지만 비교해서 길이를 제한
RoomPassword = Annotated[str, StringConstraints(max_length=20)]


class ChapterCreate(BaseModel):
    title: ChapterTitle
    start_page: int | None = Field(default=None, ge=1)


class RoomCreateRequest(BaseModel):
    book_id: int
    title: RoomTitle
    description: str | None = None
    max_capacity: int = Field(ge=2)
    start_date: datetime
    end_date: datetime
    rule: str | None = None
    is_public: bool
    password: RoomPassword | None = None
    chapters: list[ChapterCreate] = Field(default_factory=list)
    confirm_duplicate: bool = False

    @field_validator("start_date", "end_date")
    @classmethod
    def assume_utc(cls, value: datetime) -> datetime:
        # 시간대 없이 오면 UTC로 간주
        return value if value.tzinfo else value.replace(tzinfo=UTC)


class RoomCreateResponse(BaseModel):
    room_id: int
    chapters: list[ChapterItem]


class InviteLinkResponse(BaseModel):
    invite_code: str
    expires_at: datetime


class RoomPreviewResponse(BaseModel):
    room_id: int
    title: str
    description: str | None
    rule: str | None
    book_id: int
    book_title: str
    book_writer: str
    cover_image_url: str | None
    member_count: int
    max_capacity: int
    is_public: bool
    start_date: datetime
    end_date: datetime
    my_member_status: str | None


class RoomJoinRequest(BaseModel):
    password: RoomPassword | None = None
    invite_code: str | None = Field(default=None, max_length=50)


class RoomJoinResponse(BaseModel):
    room_id: int
    member_status: str


class PasswordVerifyRequest(BaseModel):
    password: Annotated[str, StringConstraints(min_length=1, max_length=20)]


class PasswordVerifyResponse(BaseModel):
    verified: bool


class WaitlistResponse(BaseModel):
    waiting_position: int
