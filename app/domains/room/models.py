from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAtMixin


class Bookroom(Base, CreatedAtMixin):
    """독서방 (ERD bookroom)."""

    __tablename__ = "bookroom"

    bookroom_id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(  # 방장 탈퇴 시 null (활성 방은 위임 후 탈퇴)
        ForeignKey("member.member_id", ondelete="SET NULL"), index=True
    )
    link: Mapped[str | None] = mapped_column(String(50))
    max_capacity: Mapped[int] = mapped_column(Integer)
    book_id: Mapped[int] = mapped_column(ForeignKey("booklist.book_id"), index=True)  # 읽는 중인 책
    title: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))
    password: Mapped[str | None] = mapped_column(String(255))
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    link_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    description: Mapped[str | None] = mapped_column(Text)
    rule: Mapped[str | None] = mapped_column(Text)
    is_public: Mapped[bool] = mapped_column(Boolean)


class BookroomMember(Base):
    """독서방 참여자 (ERD bookroom_member)."""

    __tablename__ = "bookroom_member"

    bookroom_id: Mapped[int] = mapped_column(
        ForeignKey("bookroom.bookroom_id", ondelete="CASCADE"), primary_key=True
    )
    member_id: Mapped[int] = mapped_column(
        ForeignKey("member.member_id", ondelete="CASCADE"), primary_key=True, index=True
    )
    current_chapter: Mapped[int] = mapped_column(  # 진행 챕터, 스포일러 판정(60)에 사용
        Integer, default=0, server_default="0"
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    offer_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
