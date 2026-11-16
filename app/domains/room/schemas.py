from datetime import date
from typing import Literal

from pydantic import BaseModel


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
    chapter: int
    page: int | None = None
    progress_rate: float


class RoomUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    max_capacity: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    rule: str | None = None


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
