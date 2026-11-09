from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAtMixin


class Member(Base):
    """회원 (ERD member)."""

    __tablename__ = "member"

    member_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String(50))
    pw: Mapped[str | None] = mapped_column(String(255))  # 소셜로그인 사용자는 null
    email: Mapped[str] = mapped_column(String(255), unique=True)
    marketing_select: Mapped[bool] = mapped_column(Boolean)
    preference: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String(50))  # google / kakao
    social_id: Mapped[str | None] = mapped_column(String(50))  # 소셜 고유식별자
    refresh_token_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    terms_agreed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EmailVerification(Base, CreatedAtMixin):
    """이메일 인증코드 (ERD email_verification)."""

    __tablename__ = "email_verification"

    verification_id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    code_hash: Mapped[str] = mapped_column(String(255))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Authority(Base):
    """회원 권한 기간 (ERD authority)."""

    __tablename__ = "authority"

    authority_id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(
        ForeignKey("member.member_id", ondelete="CASCADE"), index=True
    )
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    editable: Mapped[bool] = mapped_column(Boolean)
