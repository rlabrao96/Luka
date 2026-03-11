import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_get_me_requires_auth(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_returns_user_when_authenticated(app, mock_user):
    from core.security import get_current_user

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/auth/me", headers={"Authorization": "Bearer valid-token"})
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["email"] == mock_user.email
