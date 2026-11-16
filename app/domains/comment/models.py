from sqlalchemy import Boolean, ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAtMixin


class Comment(Base, CreatedAtMixin):
    """메모 댓글·대댓글 (ERD comment)."""

    __tablename__ = "comment"
    __table_args__ = (
        Index(
            "uq_comment_memo_member",
            "memo_id",
            "member_id",
            unique=True,
            postgresql_where=text("parent_id IS NULL AND is_deleted = false"),
        ),
    )

    comment_id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(
        ForeignKey("member.member_id", ondelete="CASCADE"), index=True
    )
    memo_id: Mapped[int] = mapped_column(ForeignKey("memo.memo_id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[int | None] = mapped_column(  # 대댓글이면 부모 comment_id
        ForeignKey("comment.comment_id", ondelete="CASCADE")
    )
    comment: Mapped[str] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
