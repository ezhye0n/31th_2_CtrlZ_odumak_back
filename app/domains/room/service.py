from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequest, Conflict, Forbidden, NotFound
from app.domains.room.models import Bookroom, BookroomMember
from app.domains.room.repository import RoomRepository
from app.domains.room.schemas import (
    MemberStatusUpdateResponse,
    RoomClosePreviewResponse,
    RoomHomeInfo,
    RoomHomeResponse,
    RoomMemberItem,
    RoomMembersResponse,
    RoomRulesResponse,
    RoomUpdateRequest,
)


class RoomService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = RoomRepository(db)

    async def _check_room_member(
        self, member_id: int, room_id: int
    ) -> tuple[Bookroom, BookroomMember]:
        room = await self.repo.get(room_id)
        if room is None:
            raise NotFound("ROOM_NOT_FOUND", "요청한 독서방을 찾을 수 없습니다.")

        room_member = await self.repo.get_member(room_id, member_id)
        if room_member is None:
            raise Forbidden("NOT_ROOM_MEMBER", "해당 독서방의 참여자가 아닙니다.")

        return room, room_member

    async def get_home(self, member_id: int, room_id: int) -> RoomHomeResponse:
        room, _ = await self._check_room_member(member_id, room_id)
        room_data = await self.repo.get_with_book_title(room_id)
        if room_data is None:
            raise NotFound("ROOM_NOT_FOUND", "요청한 독서방을 찾을 수 없습니다.")

        _, book_title = room_data
        role = "owner" if room.owner_id == member_id else "member"

        return RoomHomeResponse(
            room=RoomHomeInfo(
                bookroom_id=room.bookroom_id,
                title=room.title,
                book_title=book_title,
            ),
            role=role,
        )

    async def get_rules(self, member_id: int, room_id: int) -> RoomRulesResponse:
        room, _ = await self._check_room_member(member_id, room_id)

        return RoomRulesResponse(
            rule=room.rule or "",
            start_date=room.start_date.date().isoformat(),
            end_date=room.end_date.date().isoformat(),
            editable=(room.owner_id == member_id),
        )

    async def complete_member(
        self, member_id: int, room_id: int, action: Literal["stay", "leave"]
    ) -> None:
        room, room_member = await self._check_room_member(member_id, room_id)

        if action == "leave":
            if room.owner_id == member_id:
                raise Conflict(
                    "OWNER_MUST_DELEGATE",
                    "방장은 위임 후 나갈 수 있습니다.",
                )
            # TODO: 퇴장 시 개인 아카이브 저장 로직 연동 필요 시 추가
            await self.repo.delete_member(room_member)
            await self.db.commit()

    async def update_member_progress(
        self,
        member_id: int,
        room_id: int,
        chapter: int,
        page: int | None,
        progress_rate: float,
    ) -> None:
        _, room_member = await self._check_room_member(member_id, room_id)

        room_member.current_chapter = chapter
        room_member.page = page
        room_member.progress_rate = progress_rate
        await self.db.commit()

    async def _check_room_owner(self, member_id: int, room_id: int) -> Bookroom:
        room = await self.repo.get(room_id)
        if room is None:
            raise NotFound("ROOM_NOT_FOUND", "요청한 독서방을 찾을 수 없습니다.")

        if room.owner_id != member_id:
            raise Forbidden("ROOM_OWNER_ONLY", "방장만 수행할 수 있는 작업입니다.")

        return room

    async def check_manage_access(self, member_id: int, room_id: int) -> None:
        await self._check_room_owner(member_id, room_id)

    async def update_room(self, member_id: int, room_id: int, body: RoomUpdateRequest) -> None:
        room = await self._check_room_owner(member_id, room_id)

        if body.max_capacity is not None:
            current_members = await self.repo.count_members(room_id)
            if body.max_capacity < current_members:
                raise Conflict(
                    "CAPACITY_BELOW_MEMBERS",
                    "변경하려는 정원이 현재 참여 인원 수보다 적습니다.",
                )

        if body.title is not None:
            room.title = body.title
        if body.description is not None:
            room.description = body.description
        if body.max_capacity is not None:
            room.max_capacity = body.max_capacity
        if body.start_date is not None:
            room.start_date = datetime.combine(body.start_date, datetime.min.time(), tzinfo=UTC)
        if body.end_date is not None:
            room.end_date = datetime.combine(body.end_date, datetime.min.time(), tzinfo=UTC)
        if body.rule is not None:
            room.rule = body.rule

        await self.db.commit()

    async def get_room_members(self, member_id: int, room_id: int) -> RoomMembersResponse:
        room, _ = await self._check_room_member(member_id, room_id)
        rows = await self.repo.list_members_with_name(room_id)

        members = [
            RoomMemberItem(
                member_id=rm.member_id,
                name=name,
                role="owner" if room.owner_id == rm.member_id else "member",
                current_chapter=rm.current_chapter,
                page=rm.page,
                progress_rate=rm.progress_rate,
            )
            for rm, name in rows
        ]
        return RoomMembersResponse(members=members)

    async def kick_member(
        self,
        owner_member_id: int,
        room_id: int,
        target_member_id: int,
        reason: str | None = None,
    ) -> None:
        await self._check_room_owner(owner_member_id, room_id)

        if owner_member_id == target_member_id:
            raise BadRequest("CANNOT_KICK_OWNER", "방장 본인은 강퇴할 수 없습니다.")

        target_member = await self.repo.get_member(room_id, target_member_id)
        if target_member is None:
            raise NotFound("MEMBER_NOT_FOUND", "해당 독서방의 참여자를 찾을 수 없습니다.")

        # TODO: 강퇴 알림 발송 로직 연동 시 reason 활용
        await self.repo.delete_member(target_member)
        await self.db.commit()

    async def preview_close_room(
        self, member_id: int, room_id: int, room_name_confirm: str
    ) -> RoomClosePreviewResponse:
        room = await self._check_room_owner(member_id, room_id)
        return RoomClosePreviewResponse(matched=(room.title == room_name_confirm))

    async def close_room(self, member_id: int, room_id: int) -> None:
        room = await self._check_room_owner(member_id, room_id)

        # TODO: 전체 참여자 알림 발송 및 각자 아카이브(Bookrecord) 자동 저장 로직 연동
        room.status = "CLOSED"
        await self.db.commit()

    async def delegate_owner(
        self, owner_member_id: int, room_id: int, target_member_id: int
    ) -> None:
        room = await self._check_room_owner(owner_member_id, room_id)

        if owner_member_id == target_member_id:
            raise BadRequest(
                "INVALID_DELEGATE_TARGET",
                "해당 독서방의 참여자가 아니거나 본인에게는 위임할 수 없습니다.",
            )

        target_member = await self.repo.get_member(room_id, target_member_id)
        if target_member is None:
            raise BadRequest(
                "INVALID_DELEGATE_TARGET",
                "해당 독서방의 참여자가 아니거나 본인에게는 위임할 수 없습니다.",
            )

        room.owner_id = target_member_id
        await self.db.commit()

    async def update_member_status(
        self,
        member_id: int,
        room_id: int,
        status: Literal["reading", "paused", "completed"],
    ) -> MemberStatusUpdateResponse:
        _, room_member = await self._check_room_member(member_id, room_id)

        room_member.status = status
        await self.db.commit()

        next_step = "S-26" if status == "completed" else None
        return MemberStatusUpdateResponse(next_step=next_step)
