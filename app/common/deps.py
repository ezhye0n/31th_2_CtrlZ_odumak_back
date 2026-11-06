from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError

from app.common.exceptions import Unauthorized
from app.core.security import decode_token

bearer = HTTPBearer(auto_error=False)


async def get_current_user_id(
    cred: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> int:
    """Auth=필요 API에서 Depends(get_current_user_id)로 사용."""
    if cred is None:
        raise Unauthorized()
    try:
        payload = decode_token(cred.credentials)
    except PyJWTError as e:
        raise Unauthorized("유효하지 않거나 만료된 토큰입니다.") from e
    if payload.get("type") != "access":
        raise Unauthorized("access 토큰이 아닙니다.")
    return int(payload["sub"])
