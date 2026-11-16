from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import get_current_member_id
from app.common.response import ok
from app.core.database import get_db
from app.domains.comment.schemas import (
    CommentCreate,
    CommentItem,
    CommentReportCreate,
    CommentUpdate,
)
from app.domains.comment.service import CommentService

router = APIRouter(tags=["댓글"])


def get_service(db: AsyncSession = Depends(get_db)) -> CommentService:
    return CommentService(db)


@router.get("/memos/{memo_id}/comments")
async def list_comments(
    memo_id: int,
    member_id: int = Depends(get_current_member_id),
    service: CommentService = Depends(get_service),
):
    """S-23-1 한 줄 생각 조회 (72)"""
    rows = await service.list_by_memo(memo_id)
    comments = [
        CommentItem(
            comment_id=comment.comment_id,
            member_id=comment.member_id,
            name=member_name,
            memo_id=comment.memo_id,
            comment=comment.comment,
            created_at=comment.created_at,
        ).model_dump(mode="json")
        for comment, member_name in rows
    ]
    return ok({"comments": comments})


@router.post("/memos/{memo_id}/comments", status_code=status.HTTP_201_CREATED)
async def create_comment(
    memo_id: int,
    body: CommentCreate,
    member_id: int = Depends(get_current_member_id),
    service: CommentService = Depends(get_service),
):
    """S-23-2 한 줄 생각 작성 (73)"""
    comment = await service.create(member_id, memo_id, body)
    return ok({"comment_id": comment.comment_id})


@router.patch("/comments/{comment_id}")
async def update_comment(
    comment_id: int,
    body: CommentUpdate,
    member_id: int = Depends(get_current_member_id),
    service: CommentService = Depends(get_service),
):
    """S-48-1 한 줄 생각 수정 (74)"""
    comment = await service.update(member_id, comment_id, body)
    return ok({"comment_id": comment.comment_id})


@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: int,
    member_id: int = Depends(get_current_member_id),
    service: CommentService = Depends(get_service),
):
    """S-48-2 한 줄 생각 삭제 (75)"""
    deleted_type = await service.delete(member_id, comment_id)
    return ok({"deleted_type": deleted_type})


@router.post("/comments/{comment_id}/reports", status_code=status.HTTP_201_CREATED)
async def report_comment(
    comment_id: int,
    body: CommentReportCreate,
    member_id: int = Depends(get_current_member_id),
    service: CommentService = Depends(get_service),
):
    """S-49-1 신고 제출(한 줄 생각) (76)"""
    report = await service.report(member_id, comment_id, body)
    return ok({"report_id": report.report_id})
