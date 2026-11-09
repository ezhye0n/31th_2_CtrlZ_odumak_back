from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAtMixin


class Bookrecord(Base, CreatedAtMixin):
    """독서방 종료 후 남기는 독서 기록 (ERD bookrecord)."""

    __tablename__ = "bookrecord"

    record_id: Mapped[int] = mapped_column(primary_key=True)
    bookroom_id: Mapped[int] = mapped_column(
        ForeignKey("bookroom.bookroom_id", ondelete="CASCADE"), index=True
    )
    top_scene_chapter: Mapped[int] = mapped_column(Integer)  # 가장 많이 이야기한 장면의 챕터
    top_scene_memo_count: Mapped[int] = mapped_column(Integer)  # 해당 장면의 메모 수
    ai_summary: Mapped[str | None] = mapped_column(Text)  # AI 비활성·생성 실패 시 null


class BookrecordTrace(Base, CreatedAtMixin):
    """독서 기록에 담는 흔적 (ERD bookrecord_trace)."""

    __tablename__ = "bookrecord_trace"

    trace_id: Mapped[int] = mapped_column(primary_key=True)
    record_id: Mapped[int] = mapped_column(
        ForeignKey("bookrecord.record_id", ondelete="CASCADE"), index=True
    )
    memo: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str] = mapped_column(String(500))
