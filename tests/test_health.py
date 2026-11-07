from app.core.security import create_access_token, create_refresh_token


async def test_health(client):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["success"] is True


async def test_me_requires_token(client):
    res = await client.get("/api/auth/me")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


async def test_me_with_token(client):
    token = create_access_token(7)
    res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.json()["data"]["user_id"] == 7


async def test_refresh_token_rejected_as_access(client):
    token = create_refresh_token(7)
    res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
