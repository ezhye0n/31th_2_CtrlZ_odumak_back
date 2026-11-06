from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.memo.models import Memo


class MemoRepository:
    """DB 접근만 담당. 비즈니스 규칙은 service에."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, memo_id: int) -> Memo | None:
        return await self.db.get(Memo, memo_id)

    async def list_by_room(self, room_id: int) -> list[Memo]:
        stmt = select(Memo).where(Memo.room_id == room_id).order_by(Memo.created_at.desc())
        return list((await self.db.scalars(stmt)).all())

    def add(self, memo: Memo) -> None:
        self.db.add(memo)

    async def delete(self, memo: Memo) -> None:
        await self.db.delete(memo)
