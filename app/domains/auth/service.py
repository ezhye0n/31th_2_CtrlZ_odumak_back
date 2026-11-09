import json
import logging
import re
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import AppException, BadRequest, NotFound, Unauthorized
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.domains.auth import clients, tokens
from app.domains.auth.models import EmailVerification, Member
from app.domains.auth.repository import AuthRepository
from app.domains.auth.schemas import (
    CodeConfirmRequest,
    LoginRequest,
    PasswordResetRequest,
    PreferenceRequest,
    SignupRequest,
    SocialLoginRequest,
    SocialLoginResponse,
    TokenResponse,
)

logger = logging.getLogger(__name__)

CODE_EXPIRE = timedelta(minutes=5)
CODE_MAX_ATTEMPTS = 5
RESEND_INTERVAL = timedelta(minutes=5)

REQUIRED_AGREEMENTS = {"TERMS_OF_SERVICE", "PRIVACY_POLICY"}
MARKETING = "MARKETING"
PASSWORD_POLICY = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,20}$")


def _password_policy_error() -> BadRequest:
    return BadRequest(
        "PASSWORD_POLICY_VIOLATION", "비밀번호는 영문과 숫자를 포함한 8~20자로 입력해주세요."
    )


def _unsupported_provider() -> BadRequest:
    return BadRequest("UNSUPPORTED_PROVIDER", "지원하지 않는 소셜 로그인 제공자입니다.")


def _email_exists(message: str = "이미 가입된 이메일입니다.") -> AppException:
    return AppException(409, "EMAIL_ALREADY_EXISTS", message)


def _invalid_verification_token() -> AppException:
    return AppException(
        401, "INVALID_VERIFICATION_TOKEN", "이메일 인증이 만료되었습니다. 다시 인증해주세요."
    )


def _invalid_refresh_token() -> AppException:
    return AppException(
        401, "INVALID_REFRESH_TOKEN", "로그인이 만료되었습니다. 다시 로그인해주세요."
    )


def _invalid_reset_token() -> AppException:
    return AppException(
        401,
        "INVALID_RESET_TOKEN",
        "비밀번호 재설정 링크가 만료되었거나 이미 사용되었습니다. 다시 요청해주세요.",
    )


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AuthRepository(db)

    def _issue_tokens(self, member: Member) -> TokenResponse:
        # access·refresh 발급 후 refresh 해시로 저장 (commit은 호출한 쪽에서)
        refresh_token = tokens.create_refresh_token(member.member_id)
        member.refresh_token_hash = tokens.hash_token(refresh_token)
        return TokenResponse(
            member_id=member.member_id,
            access_token=create_access_token(member.member_id),
            refresh_token=refresh_token,
        )

    async def _fetch_social_profile(
        self, provider: str, social_token: str, message: str
    ) -> clients.SocialProfile:
        try:
            return await clients.fetch_social_profile(provider, social_token)
        except clients.SocialAuthError as e:
            raise AppException(401, "INVALID_SOCIAL_TOKEN", message) from e

    # S-01-1 로그인
    async def login(self, body: LoginRequest) -> TokenResponse:
        member = await self.repo.get_member_by_email(body.email)
        if member is None:
            raise NotFound("USER_NOT_FOUND", "가입되지 않은 이메일입니다.")
        # 소셜 가입 회원은 비밀번호가 없음
        if member.pw is None or not verify_password(body.password, member.pw):
            raise AppException(401, "INVALID_CREDENTIALS", "비밀번호가 올바르지 않습니다.")
        result = self._issue_tokens(member)
        await self.db.commit()
        return result

    # S-01-2 소셜 로그인 진입
    async def social_login(self, provider: str, body: SocialLoginRequest) -> SocialLoginResponse:
        if provider not in clients.SUPPORTED_PROVIDERS:
            raise _unsupported_provider()
        profile = await self._fetch_social_profile(
            provider, body.social_token, "소셜 인증에 실패했습니다. 다시 시도해주세요."
        )

        member = await self.repo.get_member_by_social(provider, profile.social_id)
        if member is not None:
            result = self._issue_tokens(member)
            await self.db.commit()
            return SocialLoginResponse(is_new_user=False, **result.model_dump())

        if profile.email:
            same_email = await self.repo.get_member_by_email(profile.email)
            if same_email is not None:
                if same_email.provider is None:
                    raise _email_exists("이미 이메일로 가입된 계정입니다. 이메일로 로그인해주세요.")
                raise BadRequest("SOCIAL_ACCOUNT", "다른 소셜 계정으로 가입된 계정입니다.")
        # 신규 회원은 S-31-2 회원가입에서 생성
        return SocialLoginResponse(is_new_user=True, has_email=profile.email is not None)

    # S-31-2 회원가입 (S-31-1 약관 동의)
    async def signup(self, body: SignupRequest) -> TokenResponse:
        if not REQUIRED_AGREEMENTS.issubset(body.required_agreements):
            raise BadRequest("REQUIRED_AGREEMENT_MISSING", "필수 약관에 모두 동의해주세요.")

        if body.signup_type == "email":
            if not PASSWORD_POLICY.match(body.password):
                raise _password_policy_error()
            if tokens.read_verification_token(body.verification_token) != body.email:
                raise _invalid_verification_token()
            member = Member(email=body.email, pw=hash_password(body.password))
        else:
            member = await self._social_member(body)

        member.marketing_select = MARKETING in body.optional_agreements
        member.terms_agreed_at = datetime.now(UTC)

        if await self.repo.get_member_by_email(member.email) is not None:
            raise _email_exists()
        self.repo.add(member)
        try:
            await self.db.flush()
        except IntegrityError as e:
            # 동시에 같은 이메일·소셜 계정으로 가입한 경우
            await self.db.rollback()
            raise _email_exists() from e
        result = self._issue_tokens(member)
        await self.db.commit()
        return result

    async def _social_member(self, body: SignupRequest) -> Member:
        if body.provider not in clients.SUPPORTED_PROVIDERS:
            raise _unsupported_provider()
        profile = await self._fetch_social_profile(
            body.provider, body.social_token, "소셜 인증이 만료되었습니다. 다시 로그인해주세요."
        )
        if await self.repo.get_member_by_social(body.provider, profile.social_id) is not None:
            raise AppException(409, "ALREADY_REGISTERED", "이미 가입된 소셜 계정입니다.")

        email = profile.email
        if email is None:
            # 제공자가 이메일을 주지 않으면 S-30-1·S-30-2로 인증한 이메일 사용
            if not (body.email and body.verification_token):
                raise BadRequest("EMAIL_REQUIRED", "이메일 인증이 필요합니다.")
            if tokens.read_verification_token(body.verification_token) != body.email:
                raise _invalid_verification_token()
            email = body.email
        return Member(email=email, provider=body.provider, social_id=profile.social_id)

    # S-30-1 인증코드 발송
    async def send_code(self, email: str) -> int:
        if await self.repo.get_member_by_email(email) is not None:
            raise _email_exists("이미 가입된 이메일입니다. 로그인해주세요.")
        await self._issue_code(email)
        return int(CODE_EXPIRE.total_seconds())

    # S-30-3 인증코드 재발송
    async def resend_code(self, email: str) -> None:
        await self._issue_code(email)

    async def _issue_code(self, email: str) -> None:
        # 기존 코드 지우고 새 코드 발급, 메일 발송 실패 시 저장X
        # S-30-1·S-30-3 모두 직전 발급 후 5분 안에 재발송 불가
        latest = await self.repo.get_latest_verification(email)
        if latest is not None and datetime.now(UTC) - latest.created_at < RESEND_INTERVAL:
            raise AppException(
                429,
                "RESEND_TOO_SOON",
                "인증코드 재발송은 이전 요청 후 5분이 지나야 가능합니다.",
            )
        code = f"{secrets.randbelow(10**6):06d}"
        await self.repo.delete_verifications(email)
        self.repo.add(
            EmailVerification(
                email=email,
                code_hash=hash_password(code),
                expires_at=datetime.now(UTC) + CODE_EXPIRE,
            )
        )
        await self.db.flush()
        try:
            await clients.send_mail(
                email,
                "[오두막 책방] 이메일 인증코드",
                f"인증코드: {code}\n5분 안에 입력해주세요.",
            )
        except clients.MailSendError as e:
            await self.db.rollback()
            raise AppException(
                502, "MAIL_SEND_FAILED", "메일 발송에 실패했습니다. 잠시 후 다시 시도해주세요."
            ) from e
        await self.db.commit()

    # S-30-2 인증코드 확인
    async def confirm_code(self, body: CodeConfirmRequest) -> str:
        verification = await self.repo.get_latest_verification(body.email)
        if verification is None or verification.expires_at <= datetime.now(UTC):
            raise BadRequest("CODE_EXPIRED", "인증코드가 만료되었습니다. 다시 받아주세요.")

        too_many = AppException(
            429, "TOO_MANY_ATTEMPTS", "인증 시도 횟수를 초과했습니다. 코드를 다시 받아주세요."
        )
        if verification.attempt_count >= CODE_MAX_ATTEMPTS:
            raise too_many
        if not verify_password(body.code, verification.code_hash):
            verification.attempt_count += 1
            await self.db.commit()
            if verification.attempt_count >= CODE_MAX_ATTEMPTS:
                raise too_many
            raise BadRequest("INVALID_CODE", "인증코드가 일치하지 않습니다.")

        await self.repo.delete_verifications(body.email)
        await self.db.commit()
        return tokens.create_verification_token(body.email)

    # S-02-1 재설정 이메일 발송
    async def request_password_reset(self, email: str) -> None:
        # 계정 존재 여부가 드러나지 않도록 결과와 상관없이 같은 응답
        member = await self.repo.get_member_by_email(email)
        if member is None or member.pw is None:
            return
        token = tokens.create_reset_token(member.member_id, member.pw)
        base_url = settings.PASSWORD_RESET_URL
        link = f"{base_url}?token={token}" if base_url else token
        try:
            await clients.send_mail(
                email,
                "[오두막 책방] 비밀번호 재설정",
                f"아래 링크에서 30분 안에 새 비밀번호를 설정해주세요.\n{link}",
            )
        except clients.MailSendError:
            logger.warning("비밀번호 재설정 메일 발송 실패: member_id=%s", member.member_id)

    # S-32-1 새 비밀번호 설정 (S-32-2 재설정 후 로그인 처리)
    async def reset_password(self, body: PasswordResetRequest) -> TokenResponse:
        if body.new_password != body.new_password_confirm:
            raise BadRequest(
                "PASSWORD_MISMATCH", "새 비밀번호와 비밀번호 확인이 일치하지 않습니다."
            )
        if not PASSWORD_POLICY.match(body.new_password):
            raise _password_policy_error()

        parsed = tokens.read_reset_token(body.token)
        if parsed is None:
            raise _invalid_reset_token()
        member_id, fingerprint = parsed
        member = await self.repo.get_member(member_id)
        # 이미 비밀번호를 바꿨다면 fingerprint가 달라 재사용 불가
        if (
            member is None
            or member.pw is None
            or not tokens.same(tokens.password_fingerprint(member.pw), fingerprint)
        ):
            raise _invalid_reset_token()

        member.pw = hash_password(body.new_password)
        result = self._issue_tokens(member)
        await self.db.commit()
        return result

    # S-01-4 토큰 갱신 (RTR)
    async def refresh(self, refresh_token: str) -> TokenResponse:
        member_id = tokens.read_refresh_token(refresh_token)
        if member_id is None:
            raise _invalid_refresh_token()
        member = await self.repo.get_member(member_id)
        if member is None:
            raise _invalid_refresh_token()
        if not tokens.same(member.refresh_token_hash, tokens.hash_token(refresh_token)):
            # 재사용 감지 시 저장 토큰도 무효화
            member.refresh_token_hash = None
            await self.db.commit()
            raise _invalid_refresh_token()
        result = self._issue_tokens(member)
        await self.db.commit()
        return result

    # S-03-1 취향 입력
    async def set_preferences(self, member_id: int, body: PreferenceRequest) -> None:
        member = await self.repo.get_member(member_id)
        if member is None:
            raise Unauthorized()
        member.preference = json.dumps(
            {"genres": body.genres, "purpose": body.purpose}, ensure_ascii=False
        )
        await self.db.commit()
