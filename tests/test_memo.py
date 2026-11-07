"""DB 없이 확인 가능한 요청 검증 테스트."""

from app.core.security import create_access_token

AUTH = {"Authorization": f"Bearer {create_access_token(1)}"}


async def test_create_requires_token(client):
    res = await client.post("/api/rooms/1/memos", json={"chapter": 1, "content": "메모"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


async def test_create_rejects_blank_content(client):
    body = {"chapter": 1, "content": "  "}
    res = await client.post("/api/rooms/1/memos", json=body, headers=AUTH)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


async def test_create_rejects_content_over_500(client):
    body = {"chapter": 1, "content": "a" * 501}
    res = await client.post("/api/rooms/1/memos", json=body, headers=AUTH)
    assert res.status_code == 400


async def test_create_requires_page_and_total_pages_together(client):
    body = {"chapter": 1, "content": "메모", "page": 10}
    res = await client.post("/api/rooms/1/memos", json=body, headers=AUTH)
    assert res.status_code == 400
    assert "함께" in res.json()["error"]["message"]


async def test_update_requires_at_least_one_field(client):
    res = await client.patch("/api/memos/1", json={}, headers=AUTH)
    assert res.status_code == 400


async def test_update_rejects_null_content(client):
    res = await client.patch("/api/memos/1", json={"content": None}, headers=AUTH)
    assert res.status_code == 400


async def test_list_rejects_unknown_sort(client):
    res = await client.get("/api/rooms/1/memos?sort=popular", headers=AUTH)
    assert res.status_code == 400
