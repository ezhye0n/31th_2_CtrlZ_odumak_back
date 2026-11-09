from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import get_current_member_id
from app.common.response import ok
from app.core.database import get_db
from app.domains.auth.schemas import (
    CodeConfirmRequest,
    EmailRequest,
    LoginRequest,
    PasswordResetRequest,
    PreferenceRequest,
    SignupRequest,
    SocialLoginRequest,
    TokenRefreshRequest,
)
from app.domains.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["온보딩·인증"])
users_router = APIRouter(prefix="/users", tags=["온보딩·인증"])  # S-03-1 취향입력용


def get_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.post("/login")
async def login(body: LoginRequest, service: AuthService = Depends(get_service)):
    """S-01-1 로그인"""
    result = await service.login(body)
    return ok(result.model_dump())


@router.post("/social/{provider}")
async def social_login(
    provider: str,
    body: SocialLoginRequest,
    service: AuthService = Depends(get_service),
):
    """S-01-2 소셜 로그인 진입"""
    result = await service.social_login(provider, body)
    return ok(result.model_dump(exclude_none=True))


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest, service: AuthService = Depends(get_service)):
    """S-31-2 회원가입 (S-31-1 약관 동의)"""
    result = await service.signup(body)
    return ok(result.model_dump())


@router.post("/email/verification-code")
async def send_verification_code(body: EmailRequest, service: AuthService = Depends(get_service)):
    """S-30-1 인증코드 발송"""
    expires_in = await service.send_code(body.email)
    return ok({"expires_in": expires_in})


@router.post("/email/verification-code/confirm")
async def confirm_verification_code(
    body: CodeConfirmRequest, service: AuthService = Depends(get_service)
):
    """S-30-2 인증코드 확인"""
    verification_token = await service.confirm_code(body)
    return ok({"verification_token": verification_token})


@router.post("/email/verification-code/resend")
async def resend_verification_code(body: EmailRequest, service: AuthService = Depends(get_service)):
    """S-30-3 인증코드 재발송"""
    await service.resend_code(body.email)
    return ok()


@router.post("/password/reset-request")
async def request_password_reset(body: EmailRequest, service: AuthService = Depends(get_service)):
    """S-02-1 재설정 이메일 발송"""
    await service.request_password_reset(body.email)
    return ok()


@router.post("/password/reset")
async def reset_password(body: PasswordResetRequest, service: AuthService = Depends(get_service)):
    """S-32-1 새 비밀번호 설정 (S-32-2 재설정 후 로그인 처리)"""
    result = await service.reset_password(body)
    return ok(result.model_dump())


@router.post("/token/refresh")
async def refresh_token(body: TokenRefreshRequest, service: AuthService = Depends(get_service)):
    """S-01-4 토큰 갱신"""
    result = await service.refresh(body.refresh_token)
    return ok(result.model_dump(exclude={"member_id"}))


@router.get("/me")
async def me(member_id: int = Depends(get_current_member_id)):
    """토큰 검증 확인용 임시 엔드포인트."""
    return ok({"member_id": member_id})


@users_router.post("/me/preferences")
async def set_preferences(
    body: PreferenceRequest,
    member_id: int = Depends(get_current_member_id),
    service: AuthService = Depends(get_service),
):
    """S-03-1 취향 입력 (S-03-2 건너뛰기)"""
    await service.set_preferences(member_id, body)
    return ok()
