from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.memo.models import Cluster, Memo, MemoReveal
from app.domains.room.models import BookroomMember


class MemoRepository:
    """DB 접근만 담당. 비즈니스 규칙은 service에."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, memo_id: int) -> Memo | None:
        return await self.db.get(Memo, memo_id)

    async def list_by_room(
        self,
        room_id: int,
        sort: Literal["latest", "oldest"],
        chapter: int | None,
        cursor: int | None,
        limit: int,
    ) -> list[Memo]:
        """memo_id 기준 커서 페이지네이션. memo_id는 작성 순서대로 증가하므로 정렬 기준으로 사용."""
        stmt = select(Memo).where(Memo.bookroom_id == room_id)
        if chapter is not None:
            stmt = stmt.where(Memo.chapter == chapter)
        if sort == "latest":
            if cursor is not None:
                stmt = stmt.where(Memo.memo_id < cursor)
            stmt = stmt.order_by(Memo.memo_id.desc())
        else:
            if cursor is not None:
                stmt = stmt.where(Memo.memo_id > cursor)
            stmt = stmt.order_by(Memo.memo_id.asc())
        return list((await self.db.scalars(stmt.limit(limit))).all())

    def add(self, memo: Memo) -> None:
        self.db.add(memo)

    async def delete(self, memo: Memo) -> None:
        await self.db.delete(memo)


class SpoilerRepository:
    """스포일러 방지 및 열람 기록 DB 접근 담당"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_memo(self, memo_id: int) -> Memo | None:
        return await self.db.get(Memo, memo_id)

    async def get_cluster(self, cluster_id: int) -> Cluster | None:
        return await self.db.get(Cluster, cluster_id)

    async def get_member_chapter(self, bookroom_id: int, member_id: int) -> int | None:
        """독서방 참여자의 현재 진행 챕터 조회 (ERD: bookroom_member.current_chapter)."""
        stmt = select(BookroomMember.current_chapter).where(
            BookroomMember.bookroom_id == bookroom_id,
            BookroomMember.member_id == member_id,
        )
        return await self.db.scalar(stmt)

    async def is_memo_revealed(self, memo_id: int, member_id: int) -> bool:
        """유저-메모 단위의 영구 열람 기록 존재 여부 확인"""
        stmt = select(MemoReveal.memo_id).where(
            MemoReveal.memo_id == memo_id,
            MemoReveal.member_id == member_id,
        )
        return (await self.db.scalar(stmt)) is not None

    async def save_memo_reveal(self, memo_id: int, member_id: int) -> None:
        """열람 기록이 없을 때만 영구 저장 (중복 호출 안전)"""
        if not await self.is_memo_revealed(memo_id, member_id):
            self.db.add(MemoReveal(memo_id=memo_id, member_id=member_id))
