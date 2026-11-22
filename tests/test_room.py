from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.common.deps import get_current_member_id
from app.core.database import get_db
from app.domains.room.service import RoomService
from app.main import app


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "url", "payload"),
    [
        ("GET", "/api/rooms/1/home", None),
        ("GET", "/api/rooms/1/rules", None),
        ("POST", "/api/rooms/1/members/me/complete", {"action": "stay"}),
        ("PATCH", "/api/rooms/1/members/me/progress", {"chapter": 1, "progress_rate": 10.0}),
        ("GET", "/api/rooms/1/manage", None),
        ("PATCH", "/api/rooms/1", {"title": "새 제목"}),
        ("GET", "/api/rooms/1/members", None),
        ("DELETE", "/api/rooms/1/members/2", None),
        ("POST", "/api/rooms/1/close/preview", {"room_name_confirm": "방 이름"}),
        ("DELETE", "/api/rooms/1", None),
        ("PATCH", "/api/rooms/1/owner", {"target_member_id": 2}),
        ("PATCH", "/api/rooms/1/members/me/status", {"status": "reading"}),
    ],
)
async def test_room_endpoints_require_auth(
    client: AsyncClient, method: str, url: str, payload: dict | None
):
    """토큰 없이 호출 시 404/405가 아닌 401이 반환되어야 한다 (라우터 등록 검증)."""
    response = await client.request(method, url, json=payload)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_room_owner_only_endpoint_returns_403_for_member(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    """방장이 아닌 일반 참여자가 방장 전용 API를 호출하면 403 ROOM_OWNER_ONLY를 반환한다."""

    async def override_current_member_id():
        return 2

    async def override_get_db():
        yield AsyncMock()

    async def mock_repo_get(self, room_id: int):
        return SimpleNamespace(bookroom_id=room_id, owner_id=1, title="테스트 방")

    app.dependency_overrides[get_current_member_id] = override_current_member_id
    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr("app.domains.room.repository.RoomRepository.get", mock_repo_get)

    try:
        response = await client.get("/api/rooms/1/manage")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "ROOM_OWNER_ONLY"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_owner_cannot_leave_before_delegate(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    """방장이 위임 없이 퇴장(action=leave)하려 하면 409 OWNER_MUST_DELEGATE를 반환한다."""

    async def override_current_member_id():
        return 1

    async def override_get_db():
        yield AsyncMock()

    async def mock_check_room_member(self, member_id: int, room_id: int):
        room = SimpleNamespace(bookroom_id=room_id, owner_id=1)
        room_member = SimpleNamespace(bookroom_id=room_id, member_id=member_id)
        return room, room_member

    app.dependency_overrides[get_current_member_id] = override_current_member_id
    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(RoomService, "_check_room_member", mock_check_room_member)

    try:
        response = await client.post("/api/rooms/1/members/me/complete", json={"action": "leave"})
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "OWNER_MUST_DELEGATE"
    finally:
        app.dependency_overrides.clear()
