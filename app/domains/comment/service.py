from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import Conflict, Forbidden, NotFound
from app.domains.comment.models import Comment
from app.domains.comment.repository import CommentRepository
from app.domains.comment.schemas import CommentCreate, CommentReportCreate, CommentUpdate
from app.domains.memo.repository import MemoRepository
from app.domains.report.models import Report


class CommentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CommentRepository(db)
        self.memo_repo = MemoRepository(db)

    """메모 존재 및 접근 가능 여부 확인 (숨김 메모 차단 + 멤버 검증 TODO)"""

    async def _get_accessible_memo(self, memo_id: int):
        memo = await self.memo_repo.get(memo_id)
        if memo is None or getattr(memo, "is_hidden", False):
            raise NotFound("MEMO_NOT_FOUND", "요청한 메모를 찾을 수 없습니다.")
        # TODO: 독서방 멤버 권한 검증(MemoService._check_room_member) 연동 필요
        return memo

    """댓글 존재 여부 확인 (없거나 삭제되었으면 404)"""

    async def _get_comment_or_404(self, comment_id: int) -> Comment:
        comment = await self.repo.get(comment_id)
        if comment is None or comment.is_deleted:
            raise NotFound("COMMENT_NOT_FOUND", "요청한 댓글을 찾을 수 없습니다.")
        return comment

    """댓글 존재 여부 + 본인 작성 여부 확인 (수정,삭제)."""

    async def _get_owned_comment(self, member_id: int, comment_id: int) -> Comment:
        comment = await self._get_comment_or_404(comment_id)
        if comment.member_id != member_id:
            raise Forbidden("SELF_ONLY", "본인이 작성/등록한 항목에 대해서만 수행할 수 있습니다.")
        return comment

    """1. 한 줄 생각 조회"""

    async def list_by_memo(self, memo_id: int) -> list[tuple[Comment, str | None]]:
        await self._get_accessible_memo(memo_id)
        return await self.repo.list_by_memo(memo_id)

    """2. 한 줄 생각 작성"""

    async def create(self, member_id: int, memo_id: int, body: CommentCreate) -> Comment:
        # 메모 존재 및 접근 가능 확인 (404)
        await self._get_accessible_memo(memo_id)

        # 메모당 사용자별 1회 중복 체크 (409)
        already_exists = await self.repo.exists_by_memo_and_member(memo_id, member_id)
        if already_exists:
            raise Conflict("ALREADY_COMMENTED", "이미 이 메모에 한 줄 생각을 남겼습니다.")

        # DB 컬럼명은 comment, 요청 필드는 content이므로 매핑해서 생성
        comment = Comment(
            member_id=member_id,
            memo_id=memo_id,
            parent_id=None,
            comment=body.content,
        )
        self.repo.add(comment)
        try:
            await self.db.commit()
        except IntegrityError as err:
            await self.db.rollback()
            raise Conflict("ALREADY_COMMENTED", "이미 이 메모에 한 줄 생각을 남겼습니다.") from err
        await self.db.refresh(comment)
        return comment

    """3. 한 줄 생각 수정"""

    async def update(self, member_id: int, comment_id: int, body: CommentUpdate) -> Comment:
        comment = await self._get_owned_comment(member_id, comment_id)
        comment.comment = body.content
        await self.db.commit()
        await self.db.refresh(comment)
        return comment

    """4. 한 줄 생각 삭제 (답글 존재 시 placeholder, 없으면 hard 삭제)"""

    async def delete(self, member_id: int, comment_id: int) -> str:
        comment = await self._get_owned_comment(member_id, comment_id)

        if await self.repo.has_replies(comment_id):
            # 답글이 있으면 본문만 placeholder로 변경하고 행은 유지
            comment.comment = "삭제된 댓글입니다."
            comment.is_deleted = True
            await self.db.commit()
            return "placeholder"

        # 답글이 없으면 DB에서 완전히 삭제
        await self.repo.delete(comment)
        await self.db.commit()
        return "hard"

    """5. 신고 제출 (한 줄 생각)"""

    async def report(self, member_id: int, comment_id: int, body: CommentReportCreate) -> Report:
        comment = await self._get_comment_or_404(comment_id)

        # 본인 댓글 신고 방지 (403)
        if comment.member_id == member_id:
            raise Forbidden("CANNOT_REPORT_OWN", "본인이 작성한 댓글은 신고할 수 없습니다.")

        # 동일 사용자 중복 신고 방지 (409)
        already_reported = await self.repo.exists_report_by_member(comment_id, member_id)
        if already_reported:
            raise Conflict("ALREADY_REPORTED", "이미 신고한 댓글입니다.")

        report = Report(
            reporter_id=member_id,
            target_member_id=comment.member_id,
            target_id=comment.comment_id,
            target_type="COMMENT",
            reason=body.reason,
            status="PENDING",
        )
        self.repo.add_report(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report
