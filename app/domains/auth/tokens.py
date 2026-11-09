"""인증 도메인 전용 토큰 (access token은 app.core.security 사용)"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import settings
from app.core.security import decode_token

VERIFICATION_EXPIRE = timedelta(minutes=30)
RESET_EXPIRE = timedelta(minutes=30)


def _encode(payload: dict, expires: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {**payload, "iat": now, "exp": now + expires}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _decode(token: str, token_type: str) -> dict | None:
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        return None
    return payload if payload.get("type") == token_type else None


def create_verification_token(email: str) -> str:
    # S-30-2 인증 성공 시 발급, S-31-2 회원가입에서 검증 (30분)
    return _encode({"type": "verification", "email": email}, VERIFICATION_EXPIRE)


def read_verification_token(token: str) -> str | None:
    payload = _decode(token, "verification")
    return payload.get("email") if payload else None


def password_fingerprint(pw_hash: str) -> str:
    # 비밀번호 변경 시 이전 재설정 토큰 무효화용
    return hashlib.sha256(pw_hash.encode()).hexdigest()[:16]


def create_reset_token(member_id: int, pw_hash: str) -> str:
    payload = {"type": "reset", "sub": str(member_id), "pwf": password_fingerprint(pw_hash)}
    return _encode(payload, RESET_EXPIRE)


def read_reset_token(token: str) -> tuple[int, str] | None:
    payload = _decode(token, "reset")
    if payload is None or "sub" not in payload or "pwf" not in payload:
        return None
    return int(payload["sub"]), payload["pwf"]


def create_refresh_token(member_id: int) -> str:
    # jti: 같은 초 재발급 시 중복 방지
    payload = {"type": "refresh", "sub": str(member_id), "jti": secrets.token_hex(8)}
    return _encode(payload, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))


def read_refresh_token(token: str) -> int | None:
    payload = _decode(token, "refresh")
    return int(payload["sub"]) if payload and "sub" in payload else None


def hash_token(token: str) -> str:
    # bcrypt는 72바이트 제한이 있어 sha256 사용
    return hashlib.sha256(token.encode()).hexdigest()


def same(a: str | None, b: str | None) -> bool:
    return a is not None and b is not None and hmac.compare_digest(a, b)
