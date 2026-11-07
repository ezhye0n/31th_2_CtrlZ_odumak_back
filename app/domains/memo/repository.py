from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.memo.models import Memo


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
        """id 기준 커서 페이지네이션. id는 작성 순서대로 증가하므로 정렬 기준으로 사용."""
        stmt = select(Memo).where(Memo.room_id == room_id)
        if chapter is not None:
            stmt = stmt.where(Memo.chapter == chapter)
        if sort == "latest":
            if cursor is not None:
                stmt = stmt.where(Memo.id < cursor)
            stmt = stmt.order_by(Memo.id.desc())
        else:
            if cursor is not None:
                stmt = stmt.where(Memo.id > cursor)
            stmt = stmt.order_by(Memo.id.asc())
        return list((await self.db.scalars(stmt.limit(limit))).all())

    def add(self, memo: Memo) -> None:
        self.db.add(memo)

    async def delete(self, memo: Memo) -> None:
        await self.db.delete(memo)
