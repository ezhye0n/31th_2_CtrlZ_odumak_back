from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAtMixin


class Report(Base, CreatedAtMixin):
    """신고 (ERD report)."""

    __tablename__ = "report"

    report_id: Mapped[int] = mapped_column(primary_key=True)
    # 회원 탈퇴(실제 삭제) 후에도 신고 기록은 남기도록 null 처리
    reporter_id: Mapped[int | None] = mapped_column(
        ForeignKey("member.member_id", ondelete="SET NULL"), index=True
    )
    target_member_id: Mapped[int | None] = mapped_column(
        ForeignKey("member.member_id", ondelete="SET NULL"), index=True
    )
    target_id: Mapped[int] = mapped_column(Integer)  # memo_id 또는 comment_id
    target_type: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))
    action_type: Mapped[str | None] = mapped_column(String(20))  # 반려/경고/콘텐츠삭제/강퇴


class Appeal(Base, CreatedAtMixin):
    """신고 처리에 대한 이의제기 (ERD appeal)."""

    __tablename__ = "appeal"

    appeal_id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("report.report_id", ondelete="CASCADE"), index=True
    )
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))
