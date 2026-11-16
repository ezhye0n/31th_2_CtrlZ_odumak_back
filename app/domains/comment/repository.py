from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.models import Member
from app.domains.comment.models import Comment
from app.domains.report.models import Report


class CommentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, comment_id: int) -> Comment | None:
        return await self.db.get(Comment, comment_id)

    async def list_by_memo(self, memo_id: int) -> list[tuple[Comment, str | None]]:
        """특정 메모에 달린 한 줄 생각 목록 + 작성자 이름(member.name) 조회"""
        stmt = (
            select(Comment, Member.name)
            .join(Member, Comment.member_id == Member.member_id)
            .where(Comment.memo_id == memo_id, Comment.parent_id.is_(None))
            .order_by(Comment.comment_id.asc())
        )
        rows = (await self.db.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows]

    async def exists_by_memo_and_member(self, memo_id: int, member_id: int) -> bool:
        """해당 사용자가 이 메모에 이미 한 줄 생각을 작성했는지 확인"""
        stmt = (
            select(Comment.comment_id)
            .where(
                Comment.memo_id == memo_id,
                Comment.member_id == member_id,
                Comment.parent_id.is_(None),
                Comment.is_deleted.is_(False),
            )
            .limit(1)
        )
        return (await self.db.scalar(stmt)) is not None

    async def has_replies(self, comment_id: int) -> bool:
        """삭제 시 해당 댓글에 달린 답글(parent_id == comment_id)이 있는지 확인."""
        stmt = select(func.count(Comment.comment_id)).where(Comment.parent_id == comment_id)
        count = await self.db.scalar(stmt)
        return (count or 0) > 0

    async def exists_report_by_member(self, comment_id: int, member_id: int) -> bool:
        """해당 사용자가 이 댓글을 이미 신고했는지 확인."""
        stmt = (
            select(Report.report_id)
            .where(
                Report.target_type == "COMMENT",
                Report.target_id == comment_id,
                Report.reporter_id == member_id,
            )
            .limit(1)
        )
        return (await self.db.scalar(stmt)) is not None

    def add(self, comment: Comment) -> None:
        self.db.add(comment)

    def add_report(self, report: Report) -> None:
        self.db.add(report)

    async def delete(self, comment: Comment) -> None:
        await self.db.delete(comment)
