from fastapi import APIRouter, Depends

from app.common.deps import get_current_user_id
from app.common.response import ok

router = APIRouter(prefix="/auth", tags=["온보딩·인증"])


@router.get("/me")
async def me(user_id: int = Depends(get_current_user_id)):
    """토큰 검증 확인용 임시 엔드포인트. 로그인·회원가입(1-14)은 여기에 추가."""
    return ok({"user_id": user_id})
