"""Alembic autogenerate가 테이블을 인식하도록 모든 도메인 모델을 여기서 import.
새 도메인 모델을 만들면 반드시 한 줄 추가할 것."""

from app.core.database import Base  # noqa: F401
from app.domains.auth.models import User  # noqa: F401
from app.domains.memo.models import Memo  # noqa: F401
