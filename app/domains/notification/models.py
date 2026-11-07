from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAtMixin


class Notification(Base, CreatedAtMixin):
    """알림 (ERD notification)."""

    __tablename__ = "notification"

    notification_id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(
        ForeignKey("member.member_id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(Text)
    deeplink: Mapped[str | None] = mapped_column(String(500))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
