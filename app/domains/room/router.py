from fastapi import APIRouter, Body, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import get_current_member_id
from app.common.response import ok
from app.core.database import get_db
from app.domains.room.schemas import (
    MemberCompleteRequest,
    MemberKickRequest,
    MemberProgressUpdateRequest,
    MemberStatusUpdateRequest,
    RoomClosePreviewRequest,
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
