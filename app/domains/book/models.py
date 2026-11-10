from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Booklist(Base):
    """등록된 책·등록 요청 (ERD booklist)."""

    __tablename__ = "booklist"

    book_id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    writer: Mapped[str] = mapped_column(String(100))
    ISBN: Mapped[str | None] = mapped_column(String(50))  # 수동 등록 시 없을 수 있음
    status: Mapped[str] = mapped_column(String(20))
    request_count: Mapped[int | None] = mapped_column(Integer)
    requester_id: Mapped[int | None] = mapped_column(
        ForeignKey("member.member_id", ondelete="SET NULL")
    )
    reject_reason: Mapped[str | None] = mapped_column(Text)
    chapters: Mapped[str | None] = mapped_column(Text)
    cover_image_url: Mapped[str | None] = mapped_column(String(500))  # 표지 이미지 (선택)
