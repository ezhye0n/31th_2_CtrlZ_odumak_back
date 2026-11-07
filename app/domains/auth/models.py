from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Member(Base):
    """회원. ERD member 테이블 기준 (담당: 주안, ERD 확정 시 함께 수정)."""

    __tablename__ = "member"

    member_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String(50))
    pw: Mapped[str | None] = mapped_column(String(255))  # 소셜로그인 사용자는 null
    email: Mapped[str] = mapped_column(String(50))
    marketing_select: Mapped[bool] = mapped_column(Boolean)
    preference: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String(50))  # google / kakao
    social_id: Mapped[str | None] = mapped_column(String(50))  # 소셜 고유식별자
    refresh_token_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    terms_agreed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
