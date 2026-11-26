"""DB 없이 확인 가능한 한 줄 생각(comment) 요청 검증 테스트."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import Conflict, Forbidden, NotFound
from app.core.security import create_access_token
from app.domains.comment.models import Comment
from app.domains.comment.schemas import CommentCreate, CommentReportCreate, CommentUpdate
from app.domains.comment.service import CommentService

AUTH = {"Authorization": f"Bearer {create_access_token(1)}"}


def _make_service() -> CommentService:
    """실제 DB 없이 Repository를 Mocking한 CommentService 생성."""
    db = AsyncMock()
    service = CommentService(db)
    service.repo = MagicMock()
    service.repo.get = AsyncMock()
    service.repo.list_by_memo = AsyncMock()
    service.repo.exists_by_memo_and_member = AsyncMock()
    service.repo.has_replies = AsyncMock()
    service.repo.exists_report_by_member = AsyncMock()
    service.repo.delete = AsyncMock()
    service.memo_repo = MagicMock()
    # 기본값: 공개 메모 + 요청자는 그 독서방의 active 참여자
    service.memo_repo.get = AsyncMock(
        return_value=SimpleNamespace(memo_id=1, bookroom_id=1, is_hidden=False)
    )
    service.memo_repo.get_room_member = AsyncMock(return_value=SimpleNamespace(member_id=1))
    return service


# 1. 한 줄 생각 조회 (GET /api/memos/{memo_id}/comments)
async def test_list_comments_requires_token(client):
    res = await client.get("/api/memos/1/comments")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


# 2. 한 줄 생각 작성 (POST /api/memos/{memo_id}/comments)
async def test_create_comment_requires_token(client):
    res = await client.post("/api/memos/1/comments", json={"content": "한 줄 생각"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


async def test_create_comment_rejects_blank_content(client):
    res = await client.post("/api/memos/1/comments", json={"content": "   "}, headers=AUTH)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


async def test_create_comment_rejects_content_over_100(client):
    res = await client.post("/api/memos/1/comments", json={"content": "a" * 101}, headers=AUTH)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


def test_create_comment_allows_100_chars_excluding_spaces():
    # 공백 포함 120자이지만 공백 제외 100자이므로 통과해야 함
    body = CommentCreate(content=("가" * 50) + (" " * 20) + ("나" * 50))
    assert len("".join(body.content.split())) == 100


async def test_create_comment_rejects_duplicate_with_409():
    service = _make_service()
    service.repo.exists_by_memo_and_member.return_value = True

    with pytest.raises(Conflict) as exc_info:
        await service.create(member_id=1, memo_id=1, body=CommentCreate(content="중복 댓글"))

    assert exc_info.value.code == "ALREADY_COMMENTED"


async def test_list_comments_rejects_hidden_memo_with_404():
    service = _make_service()
    service.memo_repo.get.return_value = SimpleNamespace(memo_id=1, bookroom_id=1, is_hidden=True)

    with pytest.raises(NotFound) as exc_info:
        await service.list_by_memo(member_id=1, memo_id=1)

    assert exc_info.value.code == "MEMO_NOT_FOUND"


# 독서방 active 참여자가 아니면(비참여자/대기/퇴장/강퇴) 조회, 작성, 신고 모두 403
async def test_list_comments_rejects_non_room_member_with_403():
    service = _make_service()
    service.memo_repo.get_room_member.return_value = None

    with pytest.raises(Forbidden) as exc_info:
        await service.list_by_memo(member_id=2, memo_id=1)

    assert exc_info.value.code == "NOT_ROOM_MEMBER"


async def test_create_comment_rejects_non_room_member_with_403():
    service = _make_service()
    service.memo_repo.get_room_member.return_value = None

    with pytest.raises(Forbidden) as exc_info:
        await service.create(member_id=2, memo_id=1, body=CommentCreate(content="한 줄 생각"))

    assert exc_info.value.code == "NOT_ROOM_MEMBER"
    service.repo.add.assert_not_called()


async def test_report_comment_rejects_non_room_member_with_403():
    service = _make_service()
    service.repo.get.return_value = Comment(
        comment_id=1, member_id=3, memo_id=1, parent_id=None, comment="타인 댓글", is_deleted=False
    )
    service.memo_repo.get_room_member.return_value = None

    with pytest.raises(Forbidden) as exc_info:
        await service.report(
            member_id=2, comment_id=1, body=CommentReportCreate(reason="신고 사유")
        )

    assert exc_info.value.code == "NOT_ROOM_MEMBER"
    service.repo.add_report.assert_not_called()


# 3. 한 줄 생각 수정 (PATCH /api/comments/{comment_id})
async def test_update_comment_requires_token(client):
    res = await client.patch("/api/comments/1", json={"content": "수정된 생각"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


async def test_update_comment_rejects_blank_content(client):
    res = await client.patch("/api/comments/1", json={"content": ""}, headers=AUTH)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


async def test_update_comment_rejects_content_over_100(client):
    res = await client.patch("/api/comments/1", json={"content": "a" * 101}, headers=AUTH)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


async def test_update_other_members_comment_raises_403():
    service = _make_service()
    service.repo.get.return_value = Comment(
        comment_id=1, member_id=2, memo_id=1, parent_id=None, comment="남의 댓글", is_deleted=False
    )

    with pytest.raises(Forbidden) as exc_info:
        await service.update(member_id=1, comment_id=1, body=CommentUpdate(content="수정 시도"))

    assert exc_info.value.code == "SELF_ONLY"


async def test_update_deleted_comment_raises_404():
    service = _make_service()
    service.repo.get.return_value = Comment(
        comment_id=1,
        member_id=1,
        memo_id=1,
        parent_id=None,
        comment="삭제된 댓글입니다.",
        is_deleted=True,
    )

    with pytest.raises(NotFound) as exc_info:
        await service.update(member_id=1, comment_id=1, body=CommentUpdate(content="재수정 시도"))

    assert exc_info.value.code == "COMMENT_NOT_FOUND"


# 4. 한 줄 생각 삭제 (DELETE /api/comments/{comment_id})
async def test_delete_comment_requires_token(client):
    res = await client.delete("/api/comments/1")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


async def test_delete_comment_without_replies_performs_hard_delete():
    service = _make_service()
    comment = Comment(
        comment_id=1, member_id=1, memo_id=1, parent_id=None, comment="원본 댓글", is_deleted=False
    )
    service.repo.get.return_value = comment
    service.repo.has_replies.return_value = False

    mode = await service.delete(member_id=1, comment_id=1)

    assert mode == "hard"
    service.repo.delete.assert_awaited_once_with(comment)
    service.db.commit.assert_awaited_once()


async def test_delete_comment_with_replies_performs_placeholder_delete():
    service = _make_service()
    comment = Comment(
        comment_id=1, member_id=1, memo_id=1, parent_id=None, comment="원본 댓글", is_deleted=False
    )
    service.repo.get.return_value = comment
    service.repo.has_replies.return_value = True

    mode = await service.delete(member_id=1, comment_id=1)

    assert mode == "placeholder"
    assert comment.comment == "삭제된 댓글입니다."
    assert comment.is_deleted is True
    service.repo.delete.assert_not_called()
    service.db.commit.assert_awaited_once()


# 5. 신고 제출 (POST /api/comments/{comment_id}/reports)
async def test_report_comment_requires_token(client):
    res = await client.post("/api/comments/1/reports", json={"reason": "부적절한 내용"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


async def test_report_comment_rejects_blank_reason(client):
    res = await client.post("/api/comments/1/reports", json={"reason": "  "}, headers=AUTH)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


async def test_report_own_comment_raises_403():
    service = _make_service()
    service.repo.get.return_value = Comment(
        comment_id=1, member_id=1, memo_id=1, parent_id=None, comment="내 댓글", is_deleted=False
    )

    with pytest.raises(Forbidden) as exc_info:
        await service.report(
            member_id=1, comment_id=1, body=CommentReportCreate(reason="신고 사유")
        )

    assert exc_info.value.code == "CANNOT_REPORT_OWN"


async def test_report_duplicate_comment_raises_409():
    service = _make_service()
    service.repo.get.return_value = Comment(
        comment_id=1, member_id=2, memo_id=1, parent_id=None, comment="타인 댓글", is_deleted=False
    )
    service.repo.exists_report_by_member.return_value = True

    with pytest.raises(Conflict) as exc_info:
        await service.report(
            member_id=1, comment_id=1, body=CommentReportCreate(reason="중복 신고")
        )

    assert exc_info.value.code == "ALREADY_REPORTED"
