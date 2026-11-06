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

    ENABLE_EMBEDDING: bool = False
    EMBEDDING_MODEL_PATH: str = "jhgan/ko-sroberta-multitask"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
