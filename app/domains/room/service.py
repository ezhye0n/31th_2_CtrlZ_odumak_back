import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import AppException, BadRequest, Conflict, Forbidden, NotFound
from app.core.security import hash_password, verify_password
from app.domains.book.schemas import ChapterItem
from app.domains.book.service import dump_chapters, load_chapters
from app.domains.notification.models import Notification
from app.domains.room.models import Bookroom, BookroomMember
from app.domains.room.repository import RoomRepository
from app.domains.room.schemas import (
    InviteLinkResponse,
    MemberStatusUpdateResponse,
    PasswordVerifyResponse,
    RoomClosePreviewResponse,
    RoomCreateRequest,
    RoomCreateResponse,
    RoomHomeInfo,
    RoomHomeResponse,
    RoomJoinRequest,
    RoomJoinResponse,
    RoomMemberItem,
    RoomMembersResponse,
    RoomPreviewResponse,
    RoomRulesResponse,
    RoomUpdateRequest,
    WaitlistResponse,
)

ROOM_OPEN = "OPEN"
ROOM_CLOSED = "CLOSED"

# bookroom_member.member_status
ACTIVE = "active"
WAITING = "waiting"
LEFT = "left"
KICKED = "kicked"

INVITE_EXPIRE = timedelta(days=7)
OFFER_EXPIRE = timedelta(hours=24)
PASSWORD_MAX_FAILS = 5
PASSWORD_LOCK = timedelta(minutes=1)

# 비밀번호 연속 실패 기록 {(room_id, member_id): (실패 횟수, 잠금 해제 시각)}
# 서버 메모리라 재시작하면 초기화되고, 워커가 여러 개면 워커마다 따로 셈
_password_failures: dict[tuple[int, int], tuple[int, datetime | None]] = {}


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
        if room_member is None or room_member.member_status != ACTIVE:
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
        if target_member is None or target_member.member_status != ACTIVE:
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

    # ---- 방 생성·참여·대기열 (22~33) ----

    async def _get_room_or_404(self, room_id: int) -> Bookroom:
        room = await self.repo.get(room_id)
        if room is None:
            raise NotFound("ROOM_NOT_FOUND", "요청한 독서방을 찾을 수 없습니다.")
        return room

    async def create_room(self, member_id: int, body: RoomCreateRequest) -> RoomCreateResponse:
        # S-10-1 독서방 생성 - 목차 저장, 중복 경고, 방장 지정까지 한 번에

        # 404 - 책이 없거나 승인 전
        book = await self.repo.get_book(body.book_id)
        if book is None or book.status != "approved":
            raise NotFound("BOOK_NOT_FOUND", "요청한 책을 찾을 수 없습니다.")

        if body.end_date <= body.start_date:
            raise BadRequest("INVALID_DATE_RANGE", "종료일은 시작일보다 뒤여야 해요.")

        has_password = bool(body.password and body.password.strip())
        if not body.is_public and not has_password:
            raise BadRequest("PASSWORD_REQUIRED", "비공개 방은 비밀번호를 입력해주세요.")

        # [23] 목차는 책 단위로 한 번만 저장, 이미 있으면 요청 목차는 무시
        chapters = load_chapters(book.chapters)
        is_new_chapters = not chapters
        if is_new_chapters:
            if len(body.chapters) < 2:
                raise BadRequest("CHAPTERS_TOO_FEW", "목차는 2개 이상 입력해주세요.")
            chapters = [
                ChapterItem(chapter_number=number, title=item.title, start_page=item.start_page)
                for number, item in enumerate(body.chapters, start=1)
            ]

        # [24] 같은 책 방에 이미 참여 중이면 한 번 더 확인받기
        if not body.confirm_duplicate and await self.repo.has_active_room_for_book(
            member_id, body.book_id
        ):
            raise Conflict(
                "DUPLICATE_BOOK_ROOM",
                "이미 같은 책을 읽는 독서방에 참여 중이에요. 그래도 만들까요?",
            )

        if is_new_chapters:
            book.chapters = dump_chapters(chapters)

        room = Bookroom(
            owner_id=member_id,
            book_id=body.book_id,
            title=body.title,
            description=body.description,
            max_capacity=body.max_capacity,
            start_date=body.start_date,
            end_date=body.end_date,
            rule=body.rule,
            is_public=body.is_public,
            password=None if body.is_public else hash_password(body.password),
            status=ROOM_OPEN,
        )
        self.repo.add(room)
        await self.db.flush()  # room_id 발급

        # [25] 방장도 참여자로 등록, 방·목차·방장을 한 번에 저장
        self.repo.add(
            BookroomMember(
                bookroom_id=room.bookroom_id,
                member_id=member_id,
                member_status=ACTIVE,
                joined_at=datetime.now(UTC),
            )
        )
        await self.db.commit()
        return RoomCreateResponse(room_id=room.bookroom_id, chapters=chapters)

    async def create_invite_link(self, member_id: int, room_id: int) -> InviteLinkResponse:
        # S-35-1 초대링크 생성 - 방장만, 다시 만들면 이전 코드 무효
        room = await self._check_room_owner(member_id, room_id)
        if room.status == ROOM_CLOSED:
            raise Conflict("ROOM_CLOSED", "종료된 독서방이에요.")

        invite_code = secrets.token_urlsafe(16)  # 22자
        expires_at = datetime.now(UTC) + INVITE_EXPIRE
        room.link = invite_code
        room.link_expires_at = expires_at
        await self.db.commit()
        return InviteLinkResponse(invite_code=invite_code, expires_at=expires_at)

    async def get_invite(self, member_id: int, invite_code: str) -> RoomPreviewResponse:
        # S-35-2 초대링크 진입·만료 확인 - 정상이면 미리보기 정보 반환
        room = await self.repo.get_by_link(invite_code)
        if room is None:
            raise NotFound("INVITE_NOT_FOUND", "유효하지 않은 초대 링크예요.")
        if not _is_valid_invite(room, invite_code):
            raise AppException(
                410, "INVITE_EXPIRED", "초대 링크가 만료되었어요. 방장에게 새 링크를 요청해주세요."
            )
        return await self.get_preview(member_id, room.bookroom_id, include_private=True)

    async def get_preview(
        self, member_id: int, room_id: int, include_private: bool = False
    ) -> RoomPreviewResponse:
        # S-11-2 방정보 미리보기 - 비공개 방 규칙은 참여·대기 중이거나 초대코드로 들어온 사람만
        await self._get_room_or_404(room_id)
        await self._release_expired_offers(room_id)

        row = await self.repo.get_with_book(room_id)
        if row is None:
            raise NotFound("ROOM_NOT_FOUND", "요청한 독서방을 찾을 수 없습니다.")
        room, book = row

        member_count = await self.repo.count_active_members(room_id)
        room_member = await self.repo.get_member(room_id, member_id)
        my_status = room_member.member_status if room_member else None
        can_see_rule = room.is_public or include_private or my_status in (ACTIVE, WAITING)
        return RoomPreviewResponse(
            room_id=room.bookroom_id,
            title=room.title,
            description=room.description,
            rule=room.rule if can_see_rule else None,
            book_id=book.book_id,
            book_title=book.title,
            book_writer=book.writer,
            cover_image_url=book.cover_image_url,
            member_count=member_count,
            max_capacity=room.max_capacity,
            is_public=room.is_public,
            start_date=room.start_date,
            end_date=room.end_date,
            my_member_status=room_member.member_status if room_member else None,
        )

    async def join_room(
        self, member_id: int, room_id: int, body: RoomJoinRequest
    ) -> RoomJoinResponse:
        # S-11-1 독서방 참여 - 비공개방은 초대코드 또는 비밀번호 확인
        room = await self._get_room_or_404(room_id)
        if room.status == ROOM_CLOSED:
            raise Conflict("ROOM_CLOSED", "종료된 독서방이에요.")

        await self._release_expired_offers(room_id)
        # 동시에 여러 명이 들어와도 정원을 넘지 않도록 방 단위로 순서대로 처리
        room = await self.repo.lock_room(room_id) or room

        room_member = await self.repo.get_member(room_id, member_id)
        current = room_member.member_status if room_member else None
        if current == KICKED:
            raise Forbidden("KICKED_FROM_ROOM", "강퇴된 독서방에는 다시 참여할 수 없어요.")
        if current == ACTIVE:
            raise Conflict("ALREADY_JOINED", "이미 참여 중인 독서방이에요.")

        if not room.is_public and not _is_valid_invite(room, body.invite_code):
            _check_password(room, member_id, body.password)

        # 우선참여권을 가진 본인은 정원 확인 없이 통과
        now = datetime.now(UTC)
        has_offer = (
            current == WAITING
            and room_member.offer_expires_at is not None
            and room_member.offer_expires_at > now
        )
        if not has_offer and await self._is_full(room, now):
            raise Conflict("ROOM_FULL", "정원이 가득 찼어요. 대기 등록을 해주세요.")

        if room_member is not None:
            room_member.member_status = ACTIVE
            room_member.offer_expires_at = None
            room_member.joined_at = now
        else:
            self.repo.add(
                BookroomMember(
                    bookroom_id=room_id, member_id=member_id, member_status=ACTIVE, joined_at=now
                )
            )
        await self.db.commit()
        return RoomJoinResponse(room_id=room_id, member_status=ACTIVE)

    async def verify_room_password(
        self, member_id: int, room_id: int, password: str
    ) -> PasswordVerifyResponse:
        # S-12-1 비밀번호 검증 - 5회 연속 실패 시 1분 잠금(S-12-2)
        room = await self._get_room_or_404(room_id)
        _check_password(room, member_id, password)
        return PasswordVerifyResponse(verified=True)

    async def join_waitlist(self, member_id: int, room_id: int) -> WaitlistResponse:
        # S-34-1 대기 등록 - 정원이 찼을 때만, 대기 순번 반환
        room = await self._get_room_or_404(room_id)
        if room.status == ROOM_CLOSED:
            raise Conflict("ROOM_CLOSED", "종료된 독서방이에요.")

        await self._release_expired_offers(room_id)
        room = await self.repo.lock_room(room_id) or room

        room_member = await self.repo.get_member(room_id, member_id)
        current = room_member.member_status if room_member else None
        if current == KICKED:
            raise Forbidden("KICKED_FROM_ROOM", "강퇴된 독서방에는 다시 참여할 수 없어요.")
        if current == ACTIVE:
            raise Conflict("ALREADY_JOINED", "이미 참여 중인 독서방이에요.")
        if current == WAITING:
            raise Conflict("ALREADY_WAITING", "이미 대기 중인 독서방이에요.")

        now = datetime.now(UTC)
        if not await self._is_full(room, now):
            raise Conflict("ROOM_NOT_FULL", "아직 자리가 있어요. 바로 참여해주세요.")

        # joined_at이 대기 순번 기준
        if room_member is not None:
            room_member.member_status = WAITING
            room_member.offer_expires_at = None
            room_member.joined_at = now
        else:
            self.repo.add(
                BookroomMember(
                    bookroom_id=room_id, member_id=member_id, member_status=WAITING, joined_at=now
                )
            )
        await self.db.flush()
        position = await self.repo.count_waiting_until(room_id, now)
        await self.db.commit()
        return WaitlistResponse(waiting_position=position)

    async def cancel_waitlist(self, member_id: int, room_id: int) -> None:
        # S-34-4 대기 취소 - 우선참여권 보유자면 다음 대기자에게 넘김
        await self._get_room_or_404(room_id)

        room_member = await self.repo.get_member(room_id, member_id)
        if room_member is None or room_member.member_status != WAITING:
            raise NotFound("WAITLIST_NOT_FOUND", "대기 중인 독서방이 아니에요.")

        had_offer = room_member.offer_expires_at is not None
        room_member.member_status = LEFT
        room_member.offer_expires_at = None
        await self.db.commit()

        if had_offer:
            await self.offer_next_waiting(room_id)

    async def offer_next_waiting(self, room_id: int) -> int | None:
        # S-34-2 우선참여권 - 퇴장·강퇴로 자리가 나면 commit 후 호출
        room = await self.repo.get(room_id)
        if room is None or room.status == ROOM_CLOSED:
            return None

        now = datetime.now(UTC)
        if await self.repo.count_offered(room_id, now) > 0:
            return None
        if await self.repo.count_active_members(room_id) >= room.max_capacity:
            return None

        next_member = await self.repo.get_first_waiting(room_id)
        if next_member is None:
            return None

        next_member.offer_expires_at = now + OFFER_EXPIRE
        self.repo.add(
            Notification(
                member_id=next_member.member_id,
                type="ROOM_SEAT_OFFERED",
                message="기다리던 독서방에 자리가 났어요. 24시간 안에 참여해주세요.",
                deeplink=f"/rooms/{room_id}",
            )
        )
        await self.db.commit()
        return next_member.member_id

    async def _release_expired_offers(self, room_id: int) -> None:
        # S-34-3 순번 이월 - 만료된 우선참여권 정리 후 다음 대기자에게
        expired = await self.repo.list_expired_offers(room_id, datetime.now(UTC))
        for room_member in expired:
            room_member.member_status = LEFT
            room_member.offer_expires_at = None
        if expired:
            await self.db.commit()
        await self.offer_next_waiting(room_id)

    async def _is_full(self, room: Bookroom, now: datetime) -> bool:
        # 정원 확인: active 인원 + 우선참여권 받은 대기자 수
        active = await self.repo.count_active_members(room.bookroom_id)
        offered = await self.repo.count_offered(room.bookroom_id, now)
        return active + offered >= room.max_capacity


def _is_valid_invite(room: Bookroom, invite_code: str | None) -> bool:
    # 이 방의 현재 초대코드이고 만료 전인지
    if not invite_code or not room.link or room.link_expires_at is None:
        return False
    if not hmac.compare_digest(room.link, invite_code):
        return False
    return room.link_expires_at > datetime.now(UTC)


def _check_password(room: Bookroom, member_id: int, password: str | None) -> None:
    # S-12-1 비밀번호 검증 - 틀리면 남은 횟수 안내, 5회 연속이면 1분 잠금(S-12-2)
    if not room.password:  # 비밀번호가 없는 방
        return

    key = (room.bookroom_id, member_id)
    now = datetime.now(UTC)
    fails, locked_until = _password_failures.get(key, (0, None))
    if locked_until is not None:
        if now < locked_until:
            raise AppException(423, "PASSWORD_LOCKED", "잠시 후 다시 시도해주세요.")
        fails = 0  # 잠금이 풀리면 처음부터

    if not password:
        raise BadRequest("PASSWORD_REQUIRED", "비밀번호를 입력해주세요.")

    if verify_password(password, room.password):
        _password_failures.pop(key, None)
        return

    fails += 1
    if fails >= PASSWORD_MAX_FAILS:
        _password_failures[key] = (fails, now + PASSWORD_LOCK)
        raise AppException(423, "PASSWORD_LOCKED", "잠시 후 다시 시도해주세요.")

    _password_failures[key] = (fails, None)
    raise BadRequest(
        "WRONG_PASSWORD",
        f"비밀번호가 올바르지 않아요. (남은 횟수 {PASSWORD_MAX_FAILS - fails}회)",
    )
