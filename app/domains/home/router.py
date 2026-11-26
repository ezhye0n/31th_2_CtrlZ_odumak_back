from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import get_current_member_id
from app.common.response import ok
from app.core.database import get_db
from app.domains.home.service import HomeService

router = APIRouter(prefix="/home", tags=["홈"])


def get_service(db: AsyncSession = Depends(get_db)) -> HomeService:
    return HomeService(db)


@router.get("/active-rooms")
async def get_active_rooms(
    limit: int | None = Query(None, ge=1, le=50),
    member_id: int = Depends(get_current_member_id),
    service: HomeService = Depends(get_service),
):
    # S-04-1 진행중인 독서방
    result = await service.get_active_rooms(member_id, limit)
    return ok(result.model_dump())


@router.get("/recommendations")
async def get_recommendations(
    member_id: int = Depends(get_current_member_id),
    service: HomeService = Depends(get_service),
):
    # S-04-2 추천 도서
    result = await service.get_recommendations(member_id)
    return ok(result.model_dump())
