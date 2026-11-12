from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.memo.models import Cluster, Memo
from app.domains.room.models import Bookroom, BookroomMember


class MemoRepository:
    """DB 접근만 담당. 비즈니스 규칙은 service에."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---- 독서방 (room 도메인 repository가 생기면 그쪽으로 이동) ----
    async def get_room(self, room_id: int) -> Bookroom | None:
        return await self.db.get(Bookroom, room_id)

    async def get_room_member(self, room_id: int, member_id: int) -> BookroomMember | None:
        return await self.db.get(BookroomMember, (room_id, member_id))

    # ---- 메모 ----
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

    # ---- 클러스터 ----
    async def get_cluster(self, cluster_id: int) -> Cluster | None:
        return await self.db.get(Cluster, cluster_id)

    def add_cluster(self, cluster: Cluster) -> None:
        self.db.add(cluster)

    async def delete_cluster(self, cluster: Cluster) -> None:
        await self.db.delete(cluster)

    async def count_cluster_memos(self, cluster_id: int) -> int:
        stmt = select(func.count()).select_from(Memo).where(Memo.cluster_id == cluster_id)
        return await self.db.scalar(stmt) or 0

    async def find_nearest_clustered_memo(
        self,
        memo: Memo,
        embedding: list[float],
        position_window: float | None,
    ) -> tuple[Memo, float] | None:
        """같은 독서방·챕터에서 클러스터가 있는 메모 중 코사인 거리가 가장 가까운 메모와 거리.
        progress_rate가 있으면 ±position_window 안의 메모만 후보로 좁힌다."""
        distance = Memo.embedding.cosine_distance(embedding)
        stmt = select(Memo, distance).where(
            Memo.bookroom_id == memo.bookroom_id,
            Memo.chapter == memo.chapter,
            Memo.embedding.is_not(None),
            Memo.cluster_id.is_not(None),
        )
        if memo.memo_id is not None:
            stmt = stmt.where(Memo.memo_id != memo.memo_id)
        if position_window is not None and memo.progress_rate is not None:
            stmt = stmt.where(
                Memo.progress_rate.between(
                    memo.progress_rate - position_window, memo.progress_rate + position_window
                )
            )
        row = (await self.db.execute(stmt.order_by(distance).limit(1))).first()
        return (row[0], float(row[1])) if row else None
