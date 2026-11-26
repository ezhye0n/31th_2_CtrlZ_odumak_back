from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.models import Member
from app.domains.book.models import Booklist
from app.domains.memo.models import Memo
from app.domains.room.models import Bookroom, BookroomMember

ACTIVE = "active"
ROOM_CLOSED = "CLOSED"
APPROVED = "approved"


class HomeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_member(self, member_id: int) -> Member | None:
        return await self.db.get(Member, member_id)

    async def list_active_rooms(
        self, member_id: int, since: datetime, limit: int | None
    ) -> list[tuple[BookroomMember, Bookroom, Booklist, int, int]]:
        # 내가 active로 참여 중인 진행 중 방 + 방별 active 인원 + since 이후 다른 사람이 쓴 메모 수
        member_count = (
            select(func.count())
            .select_from(BookroomMember)
            .where(
                BookroomMember.bookroom_id == Bookroom.bookroom_id,
                BookroomMember.member_status == ACTIVE,
            )
            .correlate(Bookroom)
            .scalar_subquery()
        )
        new_memo_count = (
            select(func.count())
            .select_from(Memo)
            .where(
                Memo.bookroom_id == Bookroom.bookroom_id,
                Memo.member_id != member_id,
                Memo.is_hidden.is_(False),
                Memo.created_at >= since,
            )
            .correlate(Bookroom)
            .scalar_subquery()
        )
        stmt = (
            select(
                BookroomMember,
                Bookroom,
                Booklist,
                member_count.label("member_count"),
                new_memo_count.label("new_memo_count"),
            )
            .join(Bookroom, Bookroom.bookroom_id == BookroomMember.bookroom_id)
            .join(Booklist, Booklist.book_id == Bookroom.book_id)
            .where(
                BookroomMember.member_id == member_id,
                BookroomMember.member_status == ACTIVE,
                Bookroom.status != ROOM_CLOSED,
            )
            .order_by(BookroomMember.joined_at.desc(), Bookroom.bookroom_id.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        rows = (await self.db.execute(stmt)).all()
        return [(row[0], row[1], row[2], row[3], row[4]) for row in rows]

    async def list_recommended_books(self, member_id: int, limit: int) -> list[Booklist]:
        # 승인된 책을 진행 중 방의 active 참여자 수가 많은 순으로, 내가 읽는 중인 책은 제외
        my_books = (
            select(Bookroom.book_id)
            .join(BookroomMember, BookroomMember.bookroom_id == Bookroom.bookroom_id)
            .where(
                BookroomMember.member_id == member_id,
                BookroomMember.member_status == ACTIVE,
                Bookroom.status != ROOM_CLOSED,
            )
        )
        reader_count = func.count(BookroomMember.member_id)
        stmt = (
            select(Booklist)
            .outerjoin(
                Bookroom,
                and_(Bookroom.book_id == Booklist.book_id, Bookroom.status != ROOM_CLOSED),
            )
            .outerjoin(
                BookroomMember,
                and_(
                    BookroomMember.bookroom_id == Bookroom.bookroom_id,
                    BookroomMember.member_status == ACTIVE,
                ),
            )
            .where(Booklist.status == APPROVED, Booklist.book_id.not_in(my_books))
            .group_by(Booklist.book_id)
            .order_by(reader_count.desc(), Booklist.book_id.desc())
            .limit(limit)
        )
        return list((await self.db.scalars(stmt)).all())
