from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

# 공백 제거 후 최소 1자 ~ 최대 100자 제한 (위반 시 자동 400/422 검증 에러)
CommentContent = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
ReportReason = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]


"""2. 한 줄 생각 작성 요청"""


class CommentCreate(BaseModel):
    content: CommentContent


"""3. 한 줄 생각 수정 요청"""


class CommentUpdate(BaseModel):
    content: CommentContent


"""5. 한 줄 생각 신고 요청"""


class CommentReportCreate(BaseModel):
    reason: ReportReason


"""1. 한 줄 생각 목록 조회 시 반환하는 댓글"""


class CommentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    comment_id: int
    member_id: int
    memo_id: int
    name: str | None
    comment: str
    created_at: datetime
