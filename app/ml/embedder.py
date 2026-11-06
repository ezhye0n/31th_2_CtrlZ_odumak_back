"""임베딩 모델 로더. ENABLE_EMBEDDING=false면 torch 없이도 서버가 뜨도록 지연 import."""

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_model = None


def load_model() -> None:
    global _model
    if not settings.ENABLE_EMBEDDING:
        logger.info("ENABLE_EMBEDDING=false, 임베딩 모델 로드 생략")
        return
    from sentence_transformers import SentenceTransformer

    logger.info("임베딩 모델 로드: %s", settings.EMBEDDING_MODEL_PATH)
    _model = SentenceTransformer(settings.EMBEDDING_MODEL_PATH, device="cpu")


def is_ready() -> bool:
    return _model is not None


def encode(texts: list[str]):
    if _model is None:
        raise RuntimeError("임베딩 모델이 로드되지 않았습니다. ENABLE_EMBEDDING을 확인하세요.")
    return _model.encode(texts, normalize_embeddings=True)
