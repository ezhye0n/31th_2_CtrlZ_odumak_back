from sqlalchemy import column, func, select, table
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.book.models import Booklist
from app.domains.room.models import Bookroom, BookroomMember


class RoomRepository:
    """DB 접근만 담당. 비즈니스 규칙은 service에."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, room_id: int) -> Bookroom | None:
        return await self.db.get(Bookroom, room_id)

    async def get_with_book_title(self, room_id: int) -> tuple[Bookroom, str] | None:
        stmt = (
            select(Bookroom, Booklist.title)
            .join(Booklist, Bookroom.book_id == Booklist.book_id)
            .where(Bookroom.bookroom_id == room_id)
        )
        row = (await self.db.execute(stmt)).first()
        if row is None:
            return None
        return row[0], row[1]

    async def get_member(self, room_id: int, member_id: int) -> BookroomMember | None:
        stmt = select(BookroomMember).where(
            BookroomMember.bookroom_id == room_id,
            BookroomMember.member_id == member_id,
        )
        return await self.db.scalar(stmt)

    async def delete_member(self, room_member: BookroomMember) -> None:
        await self.db.delete(room_member)

    async def count_members(self, room_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(BookroomMember)
            .where(BookroomMember.bookroom_id == room_id)
        )
        return await self.db.scalar(stmt) or 0

    async def list_members_with_name(self, room_id: int) -> list[tuple[BookroomMember, str | None]]:
        member_tbl = table("member", column("member_id"), column("name"))
        stmt = (
            select(BookroomMember, member_tbl.c.name)
            .outerjoin(member_tbl, BookroomMember.member_id == member_tbl.c.member_id)
            .where(BookroomMember.bookroom_id == room_id)
            .order_by(BookroomMember.joined_at.asc())
        )
        rows = (await self.db.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows]

    async def delete_room(self, room: Bookroom) -> None:
        await self.db.delete(room)
