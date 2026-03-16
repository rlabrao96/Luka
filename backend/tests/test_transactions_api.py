import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_my_transactions_requires_auth(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.get("/transactions/mine")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_my_transactions_returns_list(app, mock_user):
    from core.security import get_current_user

    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        with patch(
            "modules.transactions.service.get_my_transactions", new=AsyncMock(return_value=[])
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                response = await c.get(
                    "/transactions/mine", headers={"Authorization": "Bearer token"}
                )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
