from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.models import Member
from app.domains.book.models import Booklist
from app.domains.notification.models import Notification
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
        stmt = (
            select(BookroomMember, Member.name)
            .outerjoin(Member, BookroomMember.member_id == Member.member_id)
            .where(BookroomMember.bookroom_id == room_id)
            .order_by(BookroomMember.joined_at.asc())
        )
        rows = (await self.db.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows]

    async def delete_room(self, room: Bookroom) -> None:
        await self.db.delete(room)

    # ---- 방 생성·참여·대기열 (22~33) ----

    def add(self, instance: Bookroom | BookroomMember | Notification) -> None:
        self.db.add(instance)

    async def get_book(self, book_id: int) -> Booklist | None:
        return await self.db.get(Booklist, book_id)

    async def get_with_book(self, room_id: int) -> tuple[Bookroom, Booklist] | None:
        stmt = (
            select(Bookroom, Booklist)
            .join(Booklist, Bookroom.book_id == Booklist.book_id)
            .where(Bookroom.bookroom_id == room_id)
        )
        row = (await self.db.execute(stmt)).first()
        if row is None:
            return None
        return row[0], row[1]

    async def get_by_link(self, invite_code: str) -> Bookroom | None:
        stmt = select(Bookroom).where(Bookroom.link == invite_code).limit(1)
        return await self.db.scalar(stmt)

    async def lock_room(self, room_id: int) -> Bookroom | None:
        # 같은 방 참여·대기 요청을 하나씩 처리하도록 행 잠금 (commit 시 해제)
        stmt = (
            select(Bookroom)
            .where(Bookroom.bookroom_id == room_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return await self.db.scalar(stmt)

    async def has_active_room_for_book(self, member_id: int, book_id: int) -> bool:
        # 같은 책의 진행 중인 방에 active로 참여 중인지
        stmt = (
            select(Bookroom.bookroom_id)
            .join(BookroomMember, BookroomMember.bookroom_id == Bookroom.bookroom_id)
            .where(
                Bookroom.book_id == book_id,
                Bookroom.status != "CLOSED",
                BookroomMember.member_id == member_id,
                BookroomMember.member_status == "active",
            )
            .limit(1)
        )
        return (await self.db.scalar(stmt)) is not None

    async def count_active_members(self, room_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(BookroomMember)
            .where(
                BookroomMember.bookroom_id == room_id,
                BookroomMember.member_status == "active",
            )
        )
        return await self.db.scalar(stmt) or 0

    async def count_offered(self, room_id: int, now: datetime) -> int:
        # 만료 전 우선참여권을 받은 대기자 수
        stmt = (
            select(func.count())
            .select_from(BookroomMember)
            .where(
                BookroomMember.bookroom_id == room_id,
                BookroomMember.member_status == "waiting",
                BookroomMember.offer_expires_at > now,
            )
        )
        return await self.db.scalar(stmt) or 0

    async def list_expired_offers(self, room_id: int, now: datetime) -> list[BookroomMember]:
        stmt = select(BookroomMember).where(
            BookroomMember.bookroom_id == room_id,
            BookroomMember.member_status == "waiting",
            BookroomMember.offer_expires_at <= now,
        )
        return list((await self.db.scalars(stmt)).all())

    async def get_first_waiting(self, room_id: int) -> BookroomMember | None:
        # 우선참여권 없는 대기자 중 가장 먼저 등록한 사람
        stmt = (
            select(BookroomMember)
            .where(
                BookroomMember.bookroom_id == room_id,
                BookroomMember.member_status == "waiting",
                BookroomMember.offer_expires_at.is_(None),
            )
            .order_by(BookroomMember.joined_at.asc(), BookroomMember.member_id.asc())
            .limit(1)
        )
        return await self.db.scalar(stmt)

    async def count_waiting_until(self, room_id: int, joined_at: datetime) -> int:
        # joined_at까지 대기 등록한 사람 수 (= 대기 순번)
        stmt = (
            select(func.count())
            .select_from(BookroomMember)
            .where(
                BookroomMember.bookroom_id == room_id,
                BookroomMember.member_status == "waiting",
                BookroomMember.joined_at <= joined_at,
            )
        )
        return await self.db.scalar(stmt) or 0
