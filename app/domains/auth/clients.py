"""외부 서비스 호출 (메일 발송, 카카오·구글 토큰 검증)."""

import logging
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(5.0)
KAKAO_USER_URL = "https://kapi.kakao.com/v2/user/me"
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
SUPPORTED_PROVIDERS = ("kakao", "google")


class SocialAuthError(Exception):
    pass


class MailSendError(Exception):
    pass


@dataclass
class SocialProfile:
    social_id: str
    email: str | None  # 제공자가 검증된 이메일을 주지 않으면 None


async def fetch_social_profile(provider: str, social_token: str) -> SocialProfile:
    # provider는 SUPPORTED_PROVIDERS 중 하나, 검증 실패 시 SocialAuthError
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            if provider == "kakao":
                return await _kakao(client, social_token)
            return await _google(client, social_token)
    except httpx.HTTPError as e:
        logger.warning("%s 토큰 검증 요청 실패: %s", provider, e)
        raise SocialAuthError from e


async def _kakao(client: httpx.AsyncClient, token: str) -> SocialProfile:
    res = await client.get(KAKAO_USER_URL, headers={"Authorization": f"Bearer {token}"})
    if res.status_code != 200:
        raise SocialAuthError
    data = res.json()
    if "id" not in data:
        raise SocialAuthError
    account = data.get("kakao_account") or {}
    email = account.get("email")
    if not (account.get("is_email_valid") and account.get("is_email_verified")):
        email = None
    return SocialProfile(social_id=str(data["id"]), email=email.lower() if email else None)


async def _google(client: httpx.AsyncClient, token: str) -> SocialProfile:
    if not settings.GOOGLE_CLIENT_ID:
        logger.warning("GOOGLE_CLIENT_ID가 설정되지 않아 구글 토큰을 검증할 수 없음")
        raise SocialAuthError
    res = await client.get(GOOGLE_TOKENINFO_URL, params={"id_token": token})
    if res.status_code != 200:
        raise SocialAuthError
    data = res.json()
    if data.get("aud") != settings.GOOGLE_CLIENT_ID or not data.get("sub"):
        raise SocialAuthError
    email = data.get("email")
    if str(data.get("email_verified")).lower() != "true":
        email = None
    return SocialProfile(social_id=str(data["sub"]), email=email.lower() if email else None)


def mail_enabled() -> bool:
    return bool(settings.MAIL_API_URL and settings.MAIL_API_KEY and settings.MAIL_FROM)


async def send_mail(to: str, subject: str, text: str) -> None:
    # 메일 설정 없으면 로그로 대체 (로컬용)
    if not mail_enabled():
        logger.info("[메일 미발송] to=%s subject=%s\n%s", to, subject, text)
        return
    body = {"from": settings.MAIL_FROM, "to": [to], "subject": subject, "text": text}
    headers = {"Authorization": f"Bearer {settings.MAIL_API_KEY}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            res = await client.post(settings.MAIL_API_URL, json=body, headers=headers)
    except httpx.HTTPError as e:
        logger.warning("메일 발송 요청 실패: %s", e)
        raise MailSendError from e
    if res.status_code >= 400:
        logger.warning("메일 발송 실패: %s %s", res.status_code, res.text[:200])
        raise MailSendError
