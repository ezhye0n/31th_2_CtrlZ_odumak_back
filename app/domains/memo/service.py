from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import Forbidden, NotFound
from app.domains.memo.models import Memo
from app.domains.memo.repository import MemoRepository
from app.domains.memo.schemas import MemoCreate, MemoUpdate


class MemoService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = MemoRepository(db)

    async def _check_room_member(self, member_id: int, room_id: int) -> None:
        # TODO: rooms 도메인 생성 후 ROOM_NOT_FOUND(404), NOT_ROOM_MEMBER(403) 검사
        return None

    async def list_by_room(
        self,
        member_id: int,
        room_id: int,
        sort: Literal["latest", "oldest"],
        chapter: int | None,
        cursor: int | None,
        limit: int,
    ) -> tuple[list[Memo], int | None]:
        await self._check_room_member(member_id, room_id)
        memos = await self.repo.list_by_room(room_id, sort, chapter, cursor, limit + 1)
        next_cursor = memos[limit - 1].memo_id if len(memos) > limit else None
        return memos[:limit], next_cursor

    async def create(self, member_id: int, room_id: int, body: MemoCreate) -> Memo:
        await self._check_room_member(member_id, room_id)
        memo = Memo(member_id=member_id, bookroom_id=room_id, **body.model_dump())
        # TODO(60): 내 진행 챕터보다 앞선 챕터면 is_spoiler=True (독서방 참여 정보 확정 후)
        self.repo.add(memo)
        await self.db.commit()
        await self.db.refresh(memo)
        # TODO(61): 임베딩 → 클러스터 배정. 그전까지 cluster_id는 null
        return memo

    async def _get_owned(self, member_id: int, memo_id: int) -> Memo:
        memo = await self.repo.get(memo_id)
        if memo is None:
            raise NotFound("MEMO_NOT_FOUND", "요청한 메모를 찾을 수 없습니다.")
        if memo.member_id != member_id:
            raise Forbidden("SELF_ONLY", "본인이 작성/등록한 항목에 대해서만 수행할 수 있습니다.")
        return memo

    async def update(self, member_id: int, memo_id: int, body: MemoUpdate) -> Memo:
        memo = await self._get_owned(member_id, memo_id)
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(memo, key, value)
        # TODO(62): content가 바뀌면 임베딩 재생성 → 클러스터 재매칭
        await self.db.commit()
        await self.db.refresh(memo)
        return memo

    async def delete(self, member_id: int, memo_id: int) -> None:
        memo = await self._get_owned(member_id, memo_id)
        await self.repo.delete(memo)
        # TODO(63): 클러스터에 남은 메모가 없으면 클러스터 삭제
        await self.db.commit()
