from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppException(Exception):
    """도메인 예외는 전부 이걸 상속. code는 API 명세서의 에러 코드와 맞출 것."""

    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message


class NotFound(AppException):
    def __init__(self, message: str = "리소스를 찾을 수 없습니다."):
        super().__init__(404, "NOT_FOUND", message)


class Unauthorized(AppException):
    def __init__(self, message: str = "인증이 필요합니다."):
        super().__init__(401, "UNAUTHORIZED", message)


class Forbidden(AppException):
    def __init__(self, message: str = "권한이 없습니다."):
        super().__init__(403, "FORBIDDEN", message)


def _error_body(code: str, message: str) -> dict:
    return {"success": False, "data": None, "error": {"code": code, "message": message}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def handle_app_exception(_: Request, exc: AppException):
        return JSONResponse(status_code=exc.status_code, content=_error_body(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(x) for x in first.get("loc", [])[1:])
        msg = str(first.get("msg", "잘못된 요청입니다.")).removeprefix("Value error, ")
        message = f"{field}: {msg}" if field else msg
        return JSONResponse(status_code=422, content=_error_body("VALIDATION_ERROR", message))
