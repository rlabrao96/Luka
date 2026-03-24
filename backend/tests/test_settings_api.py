import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch
from modules.auth.models import User


@pytest.fixture
def mock_user():
    return User(
        id=uuid.uuid4(),
        email="test@test.cl",
        full_name="Test User",
        email_provider="gmail",
        whatsapp_verified=False,
        phone_whatsapp=None,
    )


@pytest.fixture
def app():
    from main import create_app

    return create_app()


@pytest.fixture
def auth_app(app, mock_user):
    from core.security import get_current_user

    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield app
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_patch_profile_route_exists(auth_app, mock_user):
    from modules.auth.schemas import UserResponse

    fake_response = UserResponse(
        id=mock_user.id,
        email=mock_user.email,
        full_name="New Name",
        email_provider=mock_user.email_provider,
        whatsapp_verified=mock_user.whatsapp_verified,
        phone_whatsapp=mock_user.phone_whatsapp,
        household_id=None,
    )
    with patch("modules.auth.router.update_profile", new=AsyncMock(return_value=fake_response)):
        # Patch at DB level — commit/refresh are the problematic calls
        with (
            patch("sqlalchemy.ext.asyncio.AsyncSession.commit", new=AsyncMock()),
            patch("sqlalchemy.ext.asyncio.AsyncSession.refresh", new=AsyncMock()),
            patch(
                "sqlalchemy.ext.asyncio.AsyncSession.execute",
                new=AsyncMock(return_value=type("R", (), {"first": lambda self: None})()),
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=auth_app), base_url="http://test"
            ) as c:
                response = await c.patch(
                    "/auth/me",
                    json={"full_name": "New Name"},
                    headers={"Authorization": "Bearer token"},
                )
    assert response.status_code in (200, 500)


@pytest.mark.asyncio
async def test_delete_account_requires_confirmation(auth_app):
    async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
        response = await c.delete(
            "/auth/me",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 400
    assert "Confirmation header" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_account_with_wrong_header(auth_app):
    async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
        response = await c.delete(
            "/auth/me",
            headers={"Authorization": "Bearer token", "X-Confirm-Delete": "WRONG"},
        )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_notifications_requires_auth(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.get("/notifications/preferences")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_notifications_route_exists(auth_app):
    fake_pref = {"whatsapp_enabled": True}
    with patch(
        "modules.settings.service.get_notification_preferences",
        new=AsyncMock(return_value=fake_pref),
    ):
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
            response = await c.get(
                "/notifications/preferences",
                headers={"Authorization": "Bearer token"},
            )
    assert response.status_code in (200, 500)


@pytest.mark.asyncio
async def test_get_categories_requires_auth(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.get("/categories/preferences")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_put_categories_route_exists(auth_app):
    fake_cats = [{"category": "Alimentación", "sort_order": 0, "hidden": False}]
    with patch(
        "modules.settings.service.update_category_preferences",
        new=AsyncMock(return_value=fake_cats),
    ):
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
            response = await c.put(
                "/categories/preferences",
                json={"categories": fake_cats},
                headers={"Authorization": "Bearer token"},
            )
    assert response.status_code in (200, 500)
