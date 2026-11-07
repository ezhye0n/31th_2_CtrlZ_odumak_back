from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppException(Exception):
    """도메인 예외는 전부 이걸 상속. code·message는 API 명세서의 Error Response와 맞출 것."""

    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message


class BadRequest(AppException):
    def __init__(self, code: str = "INVALID_INPUT", message: str = "입력값이 올바르지 않습니다."):
        super().__init__(400, code, message)


class Unauthorized(AppException):
    def __init__(self, message: str = "인증 토큰이 없거나 만료되었습니다."):
        super().__init__(401, "UNAUTHORIZED", message)


class Forbidden(AppException):
    def __init__(self, code: str = "FORBIDDEN", message: str = "권한이 없습니다."):
        super().__init__(403, code, message)


class NotFound(AppException):
    def __init__(self, code: str = "NOT_FOUND", message: str = "리소스를 찾을 수 없습니다."):
        super().__init__(404, code, message)


def _error_body(code: str, message: str) -> dict:
    return {"success": False, "data": None, "error": {"code": code, "message": message}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def handle_app_exception(_: Request, exc: AppException):
        return JSONResponse(status_code=exc.status_code, content=_error_body(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError):
        """요청 형식 오류는 명세서 공통 규칙대로 400 INVALID_INPUT."""
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(x) for x in first.get("loc", [])[1:])
        msg = str(first.get("msg", "입력값이 올바르지 않습니다.")).removeprefix("Value error, ")
        message = f"{field}: {msg}" if field else msg
        return JSONResponse(status_code=400, content=_error_body("INVALID_INPUT", message))
