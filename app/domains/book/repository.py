from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.book.models import Booklist
from app.domains.room.models import Bookroom, BookroomMember


class BookRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, book_id: int) -> Booklist | None:
        return await self.db.get(Booklist, book_id)

    async def search(self, keyword: str, status: str, limit: int) -> list[Booklist]:
        # 제목·저자·ISBN 포함 책 제목순으로 조회
        # islike 와일드카드 %, _ 는 이스케이프
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        stmt = (
            select(Booklist)
            .where(
                Booklist.status == status,
                or_(
                    Booklist.title.ilike(pattern, escape="\\"),
                    Booklist.writer.ilike(pattern, escape="\\"),
                    Booklist.ISBN.ilike(pattern, escape="\\"),
                ),
            )
            # 유니코드 순(가나다) 정렬
            .order_by(Booklist.title.collate("C").asc(), Booklist.book_id.asc())
            .limit(limit)
        )
        return list((await self.db.scalars(stmt)).all())

    async def find_same_books(
        self, title: str, writer: str, isbn: str | None, statuses: tuple[str, ...]
    ) -> list[Booklist]:
        # 중복 책 조회 - isbn이 있으면 ISBN 일치, 없으면 제목+저자 일치
        stmt = select(Booklist).where(Booklist.status.in_(statuses))
        if isbn:
            stmt = stmt.where(Booklist.ISBN == isbn)
        else:
            stmt = stmt.where(Booklist.title == title, Booklist.writer == writer)
        return list((await self.db.scalars(stmt.order_by(Booklist.book_id.asc()))).all())

    async def increase_request_count(self, book_id: int) -> None:
        # 동시에 요청이 와도 숫자가 빠지지 않게 DB +1
        stmt = (
            update(Booklist)
            .where(Booklist.book_id == book_id)
            .values(request_count=func.coalesce(Booklist.request_count, 0) + 1)
        )
        await self.db.execute(stmt)

    def add(self, book: Booklist) -> None:
        self.db.add(book)

    async def list_rooms(
        self, book_id: int, sort: str, room_filter: str | None
    ) -> list[tuple[Bookroom, int]]:
        # 책에 열린 독서방 목록 + 방마다 참여 인원(active인 bookroom_member 행 수)
        member_count = (
            select(func.count())
            .select_from(BookroomMember)
            .where(
                BookroomMember.bookroom_id == Bookroom.bookroom_id,
                BookroomMember.member_status == "active",
            )
            .correlate(Bookroom)
            .scalar_subquery()
        )
        stmt = select(Bookroom, member_count.label("member_count")).where(
            Bookroom.book_id == book_id, Bookroom.status != "CLOSED"
        )
        if room_filter == "public":
            stmt = stmt.where(Bookroom.is_public.is_(True))
        elif room_filter == "available":
            stmt = stmt.where(member_count < Bookroom.max_capacity)

        if sort == "deadline":
            stmt = stmt.order_by(Bookroom.end_date.asc(), Bookroom.bookroom_id.asc())
        else:
            stmt = stmt.order_by(Bookroom.created_at.desc(), Bookroom.bookroom_id.desc())

        rows = (await self.db.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows]
