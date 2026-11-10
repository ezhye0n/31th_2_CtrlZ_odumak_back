from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "local"
    DEBUG: bool = False
    SQL_ECHO: bool = False

    DATABASE_URL: str = "postgresql+asyncpg://odumak:odumak@localhost:5432/odumak"

    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # 구글 로그인: identity token의 aud와 비교
    GOOGLE_CLIENT_ID: str = ""

    # 메일 발송 (HTTP 메일 API). 비어 있으면 발송 대신 서버 로그에 출력
    MAIL_API_URL: str = ""
    MAIL_API_KEY: str = ""
    MAIL_FROM: str = ""
    # 비밀번호 재설정 메일에 넣을 FE 페이지 주소 (?token=... 이 붙음)
    PASSWORD_RESET_URL: str = ""

    ENABLE_EMBEDDING: bool = False
    EMBEDDING_MODEL_PATH: str = "jhgan/ko-sroberta-multitask"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
