"""Alembic autogenerate가 테이블을 인식하도록 모든 도메인 모델을 여기서 import.
새 도메인 모델을 만들면 반드시 한 줄 추가할 것."""

from app.core.database import Base  # noqa: F401
from app.domains.auth.models import EmailVerification, Member  # noqa: F401
from app.domains.book.models import Booklist  # noqa: F401
from app.domains.comment.models import Comment  # noqa: F401
from app.domains.memo.models import Attachment, Cluster, Memo, MemoReveal  # noqa: F401
from app.domains.notification.models import Notification  # noqa: F401
from app.domains.record.models import Bookrecord, BookrecordTrace  # noqa: F401
from app.domains.report.models import Appeal, Report  # noqa: F401
from app.domains.room.models import Bookroom, BookroomMember  # noqa: F401
