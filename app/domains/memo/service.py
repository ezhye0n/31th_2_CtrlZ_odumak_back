from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import Forbidden, NotFound
from app.domains.memo.models import Memo
from app.domains.memo.repository import MemoRepository
from app.domains.memo.schemas import MemoCreate, MemoUpdate


class MemoService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = MemoRepository(db)

    async def create(self, user_id: int, body: MemoCreate) -> Memo:
        memo = Memo(user_id=user_id, **body.model_dump())
        self.repo.add(memo)
        await self.db.commit()
        await self.db.refresh(memo)
        # TODO(12/27): 임베딩 → 클러스터 배정. 11/22까지는 cluster_id=None으로 임시 처리
        return memo

    async def list_by_room(self, room_id: int) -> list[Memo]:
        return await self.repo.list_by_room(room_id)

    async def _get_owned(self, user_id: int, memo_id: int) -> Memo:
        memo = await self.repo.get(memo_id)
        if memo is None:
            raise NotFound("메모를 찾을 수 없습니다.")
        if memo.user_id != user_id:
            raise Forbidden("본인 메모만 수정·삭제할 수 있습니다.")
        return memo

    async def update(self, user_id: int, memo_id: int, body: MemoUpdate) -> Memo:
        memo = await self._get_owned(user_id, memo_id)
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(memo, key, value)
        await self.db.commit()
        await self.db.refresh(memo)
        return memo

    async def delete(self, user_id: int, memo_id: int) -> None:
        memo = await self._get_owned(user_id, memo_id)
        await self.repo.delete(memo)
        await self.db.commit()
