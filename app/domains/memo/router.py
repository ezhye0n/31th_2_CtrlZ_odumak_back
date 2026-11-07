from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import get_current_user_id
from app.common.response import ok
from app.core.database import get_db
from app.domains.memo.schemas import MemoCreate, MemoItem, MemoUpdate
from app.domains.memo.service import MemoService

router = APIRouter(tags=["메모·클러스터링"])


def get_service(db: AsyncSession = Depends(get_db)) -> MemoService:
    return MemoService(db)


@router.get("/rooms/{room_id}/memos")
async def list_memos(
    room_id: int,
    sort: Literal["latest", "oldest"] = "latest",
    chapter: int | None = Query(default=None, ge=1),
    cursor: int | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    user_id: int = Depends(get_current_user_id),
    service: MemoService = Depends(get_service),
):
    """58. 메모 목록 조회"""
    memos, next_cursor = await service.list_by_room(user_id, room_id, sort, chapter, cursor, limit)
    return ok(
        {
            "memos": [MemoItem.model_validate(m).model_dump(mode="json") for m in memos],
            "next_cursor": next_cursor,
        }
    )


@router.post("/rooms/{room_id}/memos", status_code=status.HTTP_201_CREATED)
async def create_memo(
    room_id: int,
    body: MemoCreate,
    user_id: int = Depends(get_current_user_id),
    service: MemoService = Depends(get_service),
):
    """59. 메모 작성 (60 스포일러 자동판정, 61 클러스터 매칭 포함)"""
    memo = await service.create(user_id, room_id, body)
    return ok({"memo_id": memo.id, "cluster_id": memo.cluster_id, "is_spoiler": memo.is_spoiler})


@router.patch("/memos/{memo_id}")
async def update_memo(
    memo_id: int,
    body: MemoUpdate,
    user_id: int = Depends(get_current_user_id),
    service: MemoService = Depends(get_service),
):
    """62. 메모 수정"""
    memo = await service.update(user_id, memo_id, body)
    return ok({"memo_id": memo.id, "cluster_id": memo.cluster_id})


@router.delete("/memos/{memo_id}")
async def delete_memo(
    memo_id: int,
    user_id: int = Depends(get_current_user_id),
    service: MemoService = Depends(get_service),
):
    """63. 메모 삭제"""
    await service.delete(user_id, memo_id)
    return ok()
