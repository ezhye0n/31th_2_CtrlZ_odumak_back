from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import get_current_user_id
from app.common.response import ok
from app.core.database import get_db
from app.domains.memo.schemas import MemoCreate, MemoResponse, MemoUpdate
from app.domains.memo.service import MemoService

# URI는 API 명세서(58, 59, 62, 63) 확정본에 맞춰 수정
router = APIRouter(prefix="/memos", tags=["메모·클러스터링"])


def get_service(db: AsyncSession = Depends(get_db)) -> MemoService:
    return MemoService(db)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_memo(
    body: MemoCreate,
    user_id: int = Depends(get_current_user_id),
    service: MemoService = Depends(get_service),
):
    memo = await service.create(user_id, body)
    return ok(MemoResponse.model_validate(memo).model_dump(mode="json"))


@router.get("")
async def list_memos(
    room_id: int,
    _: int = Depends(get_current_user_id),
    service: MemoService = Depends(get_service),
):
    memos = await service.list_by_room(room_id)
    return ok([MemoResponse.model_validate(m).model_dump(mode="json") for m in memos])


@router.patch("/{memo_id}")
async def update_memo(
    memo_id: int,
    body: MemoUpdate,
    user_id: int = Depends(get_current_user_id),
    service: MemoService = Depends(get_service),
):
    memo = await service.update(user_id, memo_id, body)
    return ok(MemoResponse.model_validate(memo).model_dump(mode="json"))


@router.delete("/{memo_id}")
async def delete_memo(
    memo_id: int,
    user_id: int = Depends(get_current_user_id),
    service: MemoService = Depends(get_service),
):
    await service.delete(user_id, memo_id)
    return ok()
