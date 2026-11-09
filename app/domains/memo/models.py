from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAtMixin, TimestampMixin

EMBEDDING_DIM = 768  # 임베딩 모델(ko-sroberta-multitask) 출력 차원


class Cluster(Base, CreatedAtMixin):
    """의미가 비슷한 메모 묶음. 같은 독서방·챕터 안에서만 만들어짐 (61번)."""

    __tablename__ = "cluster"

    cluster_id: Mapped[int] = mapped_column(primary_key=True)
    bookroom_id: Mapped[int] = mapped_column(ForeignKey("bookroom.bookroom_id"), index=True)
    chapter: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str | None] = mapped_column(Text)  # AI 요약 캐시. 클러스터가 바뀌면 null


class Memo(Base, TimestampMixin):
    """독서 메모. 페이지 상대 위치(page / total_pages)는 클러스터링 후보 축소에 사용."""

    __tablename__ = "memo"

    memo_id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(
        ForeignKey("member.member_id", ondelete="CASCADE"), index=True
    )
    bookroom_id: Mapped[int] = mapped_column(ForeignKey("bookroom.bookroom_id"), index=True)
    cluster_id: Mapped[int | None] = mapped_column(  # AI 비활성·매칭 전에는 null
        ForeignKey("cluster.cluster_id", ondelete="SET NULL"), index=True
    )
    chapter: Mapped[int] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer)
    total_pages: Mapped[int | None] = mapped_column(Integer)
    progress_rate: Mapped[float | None] = mapped_column(Float)  # page / total_pages, 없으면 null
    quote: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    is_spoiler: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))


class MemoReveal(Base):
    """스포일러로 가려진 메모를 회원이 열람한 기록 (ERD memo_reveal)."""

    __tablename__ = "memo_reveal"

    memo_id: Mapped[int] = mapped_column(
        ForeignKey("memo.memo_id", ondelete="CASCADE"), primary_key=True
    )
    member_id: Mapped[int] = mapped_column(
        ForeignKey("member.member_id", ondelete="CASCADE"), primary_key=True
    )
    revealed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Attachment(Base, CreatedAtMixin):
    """메모에 첨부한 독서 흔적 이미지 (ERD attachment, 97~99번)."""

    __tablename__ = "attachment"

    attachment_id: Mapped[int] = mapped_column(primary_key=True)
    memo_id: Mapped[int] = mapped_column(ForeignKey("memo.memo_id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(500))
