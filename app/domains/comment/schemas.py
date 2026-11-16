from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

# 공백 제거 후 최소 1자 ~ 최대 100자 제한 (위반 시 자동 400/422 검증 에러)
CommentContent = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ReportReason = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]


def _validate_content_length_without_spaces(v: str) -> str:
    length_without_spaces = len("".join(v.split()))
    if length_without_spaces == 0:
        raise ValueError("내용을 입력해 주세요.")
    if length_without_spaces > 100:
        raise ValueError("공백 제외 100자 이하로 입력해 주세요.")
    return v


"""2. 한 줄 생각 작성 요청"""


class CommentCreate(BaseModel):
    content: CommentContent

    @field_validator("content")
    @classmethod
    def check_len(cls, v: str) -> str:
        return _validate_content_length_without_spaces(v)


"""3. 한 줄 생각 수정 요청"""


class CommentUpdate(BaseModel):
    content: CommentContent

    @field_validator("content")
    @classmethod
    def check_len(cls, v: str) -> str:
        return _validate_content_length_without_spaces(v)


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
