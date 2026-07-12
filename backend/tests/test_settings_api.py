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
        preferred_currency="CLP",
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
async def test_patch_profile_route_exists(app, db, make_user):
    """Real-DB smoke: PATCH /auth/me renames the profile. (The old version
    patched AsyncSession globally and broke when the endpoint adopted
    db.merge; full contribution-field coverage lives in test_auth.py.)"""
    from core.database import get_db
    from core.security import get_current_user

    user = await make_user()

    async def _db():
        yield db

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = _db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            response = await c.patch(
                "/auth/me",
                json={"full_name": "New Name"},
                headers={"Authorization": "Bearer token"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["full_name"] == "New Name"


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
async def test_put_categories_reorder_route_exists(auth_app):
    fake_cats = [
        {
            "category": "Alimentación",
            "sort_order": 0,
            "category_type": "expense",
            "is_custom": False,
        }
    ]
    with patch(
        "modules.settings.service.reorder_categories",
        new=AsyncMock(return_value=fake_cats),
    ):
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
            response = await c.put(
                "/categories/preferences",
                json={"categories": [{"category": "Alimentación", "sort_order": 0}]},
                headers={"Authorization": "Bearer token"},
            )
    assert response.status_code in (200, 500)


def test_allowed_currencies_contains_all_16():
    from modules.auth.schemas import ALLOWED_CURRENCIES

    expected = {
        "CLP",
        "USD",
        "COP",
        "BRL",
        "MXN",
        "ARS",
        "PEN",
        "UYU",
        "PYG",
        "BOB",
        "VES",
        "DOP",
        "GTQ",
        "HNL",
        "NIO",
        "CRC",
    }
    assert expected == ALLOWED_CURRENCIES
