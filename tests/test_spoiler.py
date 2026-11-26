"""스포일러 방지(68~71) 요청 검증 및 챕터 비교 단위 테스트"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import Forbidden
from app.core.security import create_access_token
from app.domains.memo.service import SpoilerService

AUTH = {"Authorization": f"Bearer {create_access_token(1)}"}


# 68. 진행챕터 비교 (S-21-1) 단위 테스트
def test_is_chapter_spoiler_logic():
    service = SpoilerService(db=None)  # type: ignore[arg-type]
    # 이미 읽은 챕터(메모 챕터 <= 진행 챕터)면 스포일러 아님(False)
    assert service.is_chapter_spoiler(target_chapter=3, current_chapter=5) is False
    assert service.is_chapter_spoiler(target_chapter=5, current_chapter=5) is False
    # 아직 안 읽은 챕터(메모 챕터 > 진행 챕터)면 스포일러(True)
    assert service.is_chapter_spoiler(target_chapter=6, current_chapter=5) is True
    # 독서방 참여 기록이 없으면(None) 안전하게 스포일러(True) 처리
    assert service.is_chapter_spoiler(target_chapter=1, current_chapter=None) is True


# 69. 블러 처리 및 경고 열람 (GET /api/memos/{memo_id}/reveal-check)
async def test_reveal_check_requires_token(client):
    res = await client.get("/api/memos/1/reveal-check")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


# 70. 1회 열람 시 영구 해제 (POST /api/memos/{memo_id}/reveal)
async def test_reveal_memo_requires_token(client):
    res = await client.post("/api/memos/1/reveal")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


# 69, 70. 독서방 active 참여자가 아니면(비참여자/대기/퇴장/강퇴) 블러 확인과 열람 해제 모두 403
async def test_reveal_rejects_non_room_member_with_403():
    service = SpoilerService(db=AsyncMock())
    service.repo = MagicMock()
    service.repo.get_memo = AsyncMock(
        return_value=SimpleNamespace(memo_id=1, bookroom_id=1, member_id=3, chapter=1)
    )
    service.repo.save_memo_reveal = AsyncMock()
    service.memo_repo = MagicMock()
    service.memo_repo.get_room_member = AsyncMock(return_value=None)

    with pytest.raises(Forbidden) as exc_info:
        await service.check_reveal(member_id=2, memo_id=1)
    assert exc_info.value.code == "NOT_ROOM_MEMBER"

    with pytest.raises(Forbidden) as exc_info:
        await service.reveal_memo(member_id=2, memo_id=1)
    assert exc_info.value.code == "NOT_ROOM_MEMBER"
    service.repo.save_memo_reveal.assert_not_called()
