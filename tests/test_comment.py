"""DB 없이 확인 가능한 한 줄 생각(comment) 요청 검증 테스트."""

from app.core.security import create_access_token

AUTH = {"Authorization": f"Bearer {create_access_token(1)}"}


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


# 4. 한 줄 생각 삭제 (DELETE /api/comments/{comment_id})
async def test_delete_comment_requires_token(client):
    res = await client.delete("/api/comments/1")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


# 5. 신고 제출 (POST /api/comments/{comment_id}/reports)
async def test_report_comment_requires_token(client):
    res = await client.post("/api/comments/1/reports", json={"reason": "부적절한 내용"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


async def test_report_comment_rejects_blank_reason(client):
    res = await client.post("/api/comments/1/reports", json={"reason": "  "}, headers=AUTH)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"
