from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """모든 성공 응답 공통 포맷: {"success": true, "data": ..., "error": null}"""

    success: bool = True
    data: T | None = None
    error: None = None


def ok(data=None) -> dict:
    return {"success": True, "data": data, "error": None}
