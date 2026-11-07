from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class Memo(Base, TimestampMixin):
    """독서 메모. 페이지 상대 위치(page / total_pages)는 클러스터링 후보 축소에 사용."""

    __tablename__ = "memos"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    room_id: Mapped[int] = mapped_column(Integer, index=True)  # rooms 테이블 생성 후 FK로 변경
    chapter: Mapped[int] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer)
    total_pages: Mapped[int | None] = mapped_column(Integer)
    quote: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    is_spoiler: Mapped[bool] = mapped_column(Boolean, default=False)
    cluster_id: Mapped[int | None] = mapped_column(Integer, index=True)  # AI 비활성 시 null
