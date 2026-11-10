import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.common.exceptions import register_exception_handlers
from app.common.response import ok
from app.core.config import settings
from app.core.database import engine
from app.domains.auth.router import router as auth_router
from app.domains.auth.router import users_router
from app.domains.memo.router import router as memo_router
from app.ml import embedder

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    embedder.load_model()  # 서버 기동 시 1회 로드
    yield
    await engine.dispose()


app = FastAPI(
    title="오두막 책방 API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.APP_ENV != "prod" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)


@app.get("/health", tags=["system"])
async def health():
    return ok({"status": "ok", "env": settings.APP_ENV, "embedding": embedder.is_ready()})


@app.get("/health/db", tags=["system"])
async def health_db():
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return ok({"db": "ok"})


api = APIRouter(prefix="/api")
api.include_router(auth_router)
api.include_router(users_router)
api.include_router(memo_router)
# 담당 도메인 라우터는 여기 한 줄씩 추가 (room, community, notification ...)
app.include_router(api)
