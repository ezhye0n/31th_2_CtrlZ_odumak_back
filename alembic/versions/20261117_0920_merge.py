"""merge

Revision ID: a565d2ef3d91
Revises: 3b6f81f97c91, 286b798c632a
Create Date: 2026-11-17 09:20:19.576052
"""

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401  (vector 컬럼용)

revision: str = "a565d2ef3d91"
down_revision: str | None = ("3b6f81f97c91", "286b798c632a")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
