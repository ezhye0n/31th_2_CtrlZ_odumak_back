from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import Forbidden, NotFound
from app.domains.memo.clustering import ClusterMatcher
from app.domains.memo.models import Memo
from app.domains.memo.repository import MemoRepository
from app.domains.memo.schemas import MemoCreate, MemoUpdate
from app.domains.room.models import BookroomMember


class MemoService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = MemoRepository(db)
        self.matcher = ClusterMatcher(self.repo)

    async def _check_room_member(self, member_id: int, room_id: int) -> BookroomMember:
        if await self.repo.get_room(room_id) is None:
            raise NotFound("ROOM_NOT_FOUND", "요청한 독서방을 찾을 수 없습니다.")
        room_member = await self.repo.get_room_member(room_id, member_id)
        if room_member is None:
            raise Forbidden("NOT_ROOM_MEMBER", "독서방 참여자만 이용할 수 있습니다.")
        return room_member

    @staticmethod
    def _judge_spoiler(chapter: int, marked: bool, room_member: BookroomMember | None) -> bool:
        """60. 작성자 진행 챕터보다 뒤 챕터면 자동 스포일러. 직접 표시와 OR."""
        auto = room_member is not None and chapter > room_member.current_chapter
        return marked or auto

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
        room_member = await self._check_room_member(member_id, room_id)
        memo = Memo(member_id=member_id, bookroom_id=room_id, **body.model_dump())
        if body.page is not None and body.total_pages is not None:
            memo.progress_rate = body.page / body.total_pages
        memo.is_spoiler = self._judge_spoiler(body.chapter, body.is_spoiler, room_member)
        await self.matcher.assign(memo)
        self.repo.add(memo)
        await self.db.commit()
        await self.db.refresh(memo)
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
        values = body.model_dump(exclude_unset=True)

        if "is_spoiler" in values:
            room_member = await self.repo.get_room_member(memo.bookroom_id, member_id)
            memo.is_spoiler = self._judge_spoiler(memo.chapter, values["is_spoiler"], room_member)

        if "content" in values and values["content"] != memo.content:
            old_cluster_id = memo.cluster_id
            memo.content = values["content"]
            memo.embedding = None
            memo.cluster_id = None
            await self.db.flush()  # 기존 클러스터에서 먼저 빠져야 재매칭 후보에서 제외됨
            await self.matcher.assign(memo)
            await self.db.flush()
            if memo.cluster_id != old_cluster_id:
                await self.matcher.cleanup(old_cluster_id)

        await self.db.commit()
        await self.db.refresh(memo)
        return memo

    async def delete(self, member_id: int, memo_id: int) -> None:
        memo = await self._get_owned(member_id, memo_id)
        cluster_id = memo.cluster_id
        await self.repo.delete(memo)
        await self.db.flush()
        await self.matcher.cleanup(cluster_id)
        await self.db.commit()
