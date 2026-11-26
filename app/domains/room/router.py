from fastapi import APIRouter, Body, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import get_current_member_id
from app.common.response import ok
from app.core.database import get_db
from app.domains.room.schemas import (
    MemberCompleteRequest,
    MemberKickRequest,
    MemberProgressUpdateRequest,
    MemberStatusUpdateRequest,
    PasswordVerifyRequest,
    RoomClosePreviewRequest,
    RoomCreateRequest,
    RoomJoinRequest,
    RoomOwnerDelegateRequest,
    RoomUpdateRequest,
)
from app.domains.room.service import RoomService

router = APIRouter(prefix="/rooms", tags=["room"])


@router.get("/{room_id}/home")
async def get_room_home(
    room_id: int,
    member_id: int = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    data = await RoomService(db).get_home(member_id=member_id, room_id=room_id)
    return ok(data)


@router.get("/{room_id}/rules")
async def get_room_rules(
    room_id: int,
    member_id: int = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    data = await RoomService(db).get_rules(member_id=member_id, room_id=room_id)
    return ok(data)


@router.post("/{room_id}/members/me/complete")
async def complete_room_member(
    room_id: int,
    body: MemberCompleteRequest,
    member_id: int = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    await RoomService(db).complete_member(member_id=member_id, room_id=room_id, action=body.action)
    return ok(None)


@router.patch("/{room_id}/members/me/progress")
async def update_my_progress(
    room_id: int,
    body: MemberProgressUpdateRequest,
    member_id: int = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    await RoomService(db).update_member_progress(
        member_id=member_id,
        room_id=room_id,
        chapter=body.chapter,
        page=body.page,
        progress_rate=body.progress_rate,
    )
    return ok(None)


@router.get("/{room_id}/manage")
async def get_room_manage(
    room_id: int,
    member_id: int = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    await RoomService(db).check_manage_access(member_id=member_id, room_id=room_id)
    return ok(None)


@router.patch("/{room_id}")
async def update_room(
    room_id: int,
    body: RoomUpdateRequest,
    member_id: int = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    await RoomService(db).update_room(member_id=member_id, room_id=room_id, body=body)
    return ok(None)


@router.get("/{room_id}/members")
async def get_room_members(
    room_id: int,
    member_id: int = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    data = await RoomService(db).get_room_members(member_id=member_id, room_id=room_id)
    return ok(data)


@router.delete("/{room_id}/members/{member_id}")
async def kick_room_member(
    room_id: int,
    target_member_id: int = Path(..., alias="member_id"),
    body: MemberKickRequest | None = Body(default=None),
    member_id: int = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    await RoomService(db).kick_member(
        owner_member_id=member_id,
        room_id=room_id,
        target_member_id=target_member_id,
        reason=body.reason if body else None,
    )
    return ok(None)


@router.post("/{room_id}/close/preview")
async def preview_close_room(
    room_id: int,
    body: RoomClosePreviewRequest,
    member_id: int = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    data = await RoomService(db).preview_close_room(
        member_id=member_id,
        room_id=room_id,
        room_name_confirm=body.room_name_confirm,
    )
    return ok(data)


@router.delete("/{room_id}")
async def close_room(
    room_id: int,
    member_id: int = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    await RoomService(db).close_room(member_id=member_id, room_id=room_id)
    return ok(None)


@router.patch("/{room_id}/owner")
async def delegate_room_owner(
    room_id: int,
    body: RoomOwnerDelegateRequest,
    member_id: int = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    await RoomService(db).delegate_owner(
        owner_member_id=member_id,
        room_id=room_id,
        target_member_id=body.target_member_id,
    )
    return ok(None)


@router.patch("/{room_id}/members/me/status")
async def update_my_status(
    room_id: int,
    body: MemberStatusUpdateRequest,
    member_id: int = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    data = await RoomService(db).update_member_status(
        member_id=member_id, room_id=room_id, status=body.status
    )
    return ok(data)


# ---- 방 생성·참여·대기열 (22~33) ----


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_room(
    body: RoomCreateRequest,
    member_id: int = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    # S-10-1 독서방 생성 - 목차 저장, 중복 경고, 방장 지정까지 한 번에
    data = await RoomService(db).create_room(member_id=member_id, body=body)
    return ok(data)


@router.get("/{room_id}")
async def get_room_preview(
    room_id: int,
    member_id: int = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    # S-11-2 방정보 미리보기 - 만료된 우선참여권 정리 후 조회
    data = await RoomService(db).get_preview(member_id=member_id, room_id=room_id)
    return ok(data)


@router.post("/{room_id}/join")
async def join_room(
    room_id: int,
    body: RoomJoinRequest | None = Body(default=None),
    member_id: int = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    # S-11-1 독서방 참여 - 비공개방은 초대코드 또는 비밀번호 확인
    data = await RoomService(db).join_room(
        member_id=member_id, room_id=room_id, body=body or RoomJoinRequest()
    )
    return ok(data)


@router.post("/{room_id}/verify-password")
async def verify_room_password(
    room_id: int,
    body: PasswordVerifyRequest,
    member_id: int = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    # S-12-1 비밀번호 검증 - 5회 연속 실패 시 1분 잠금(S-12-2)
    data = await RoomService(db).verify_room_password(
        member_id=member_id, room_id=room_id, password=body.password
    )
    return ok(data)


@router.post("/{room_id}/invite-link")
async def create_invite_link(
    room_id: int,
    member_id: int = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    # S-35-1 초대링크 생성 - 방장만, 다시 만들면 이전 코드 무효
    data = await RoomService(db).create_invite_link(member_id=member_id, room_id=room_id)
    return ok(data)


@router.post("/{room_id}/waitlist")
async def join_waitlist(
    room_id: int,
    member_id: int = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    # S-34-1 대기 등록 - 정원이 찼을 때만, 대기 순번 반환
    data = await RoomService(db).join_waitlist(member_id=member_id, room_id=room_id)
    return ok(data)


@router.delete("/{room_id}/waitlist")
async def cancel_waitlist(
    room_id: int,
    member_id: int = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    # S-34-4 대기 취소 - 우선참여권 보유자면 다음 대기자에게 넘김
    await RoomService(db).cancel_waitlist(member_id=member_id, room_id=room_id)
    return ok(None)


invite_router = APIRouter(prefix="/invites", tags=["room"])


@invite_router.get("/{invite_code}")
async def get_invite(
    invite_code: str,
    member_id: int = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    # S-35-2 초대링크 진입·만료 확인
    data = await RoomService(db).get_invite(member_id=member_id, invite_code=invite_code)
    return ok(data)
