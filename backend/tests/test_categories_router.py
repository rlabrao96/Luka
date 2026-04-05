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


_FAKE_CATS = [
    {"category": "Alimentación", "sort_order": 0, "category_type": "expense", "is_custom": False},
    {"category": "Sueldo", "sort_order": 0, "category_type": "income", "is_custom": False},
]


@pytest.mark.asyncio
async def test_get_categories_returns_200(auth_app):
    with patch(
        "modules.settings.service.get_category_preferences",
        new=AsyncMock(return_value=_FAKE_CATS),
    ):
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
            r = await c.get("/categories/preferences", headers={"Authorization": "Bearer token"})
    assert r.status_code == 200
    data = r.json()
    assert "categories" in data
    assert data["categories"][0]["category_type"] == "expense"


@pytest.mark.asyncio
async def test_get_categories_no_hidden_field(auth_app):
    """Response must NOT include 'hidden' field."""
    with patch(
        "modules.settings.service.get_category_preferences",
        new=AsyncMock(return_value=_FAKE_CATS),
    ):
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
            r = await c.get("/categories/preferences", headers={"Authorization": "Bearer token"})
    assert "hidden" not in r.json()["categories"][0]


@pytest.mark.asyncio
async def test_put_categories_reorder(auth_app):
    with patch(
        "modules.settings.service.reorder_categories",
        new=AsyncMock(return_value=_FAKE_CATS),
    ):
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
            r = await c.put(
                "/categories/preferences",
                json={"categories": [{"category": "Alimentación", "sort_order": 0}]},
                headers={"Authorization": "Bearer token"},
            )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_put_categories_mismatch_returns_422(auth_app):
    with patch(
        "modules.settings.service.reorder_categories",
        new=AsyncMock(side_effect=ValueError("mismatch")),
    ):
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
            r = await c.put(
                "/categories/preferences",
                json={"categories": [{"category": "Alimentación", "sort_order": 0}]},
                headers={"Authorization": "Bearer token"},
            )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_add_category_returns_201(auth_app):
    new_cat = {"category": "Mascotas", "sort_order": 14, "category_type": "expense", "is_custom": True}
    with patch(
        "modules.settings.service.add_category",
        new=AsyncMock(return_value=new_cat),
    ):
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
            r = await c.post(
                "/categories/preferences",
                json={"category": "Mascotas", "category_type": "expense"},
                headers={"Authorization": "Bearer token"},
            )
    assert r.status_code == 201
    assert r.json()["category"] == "Mascotas"


@pytest.mark.asyncio
async def test_post_add_category_at_limit_returns_422(auth_app):
    with patch(
        "modules.settings.service.add_category",
        new=AsyncMock(side_effect=ValueError("Limit of 19")),
    ):
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
            r = await c.post(
                "/categories/preferences",
                json={"category": "Nueva", "category_type": "expense"},
                headers={"Authorization": "Bearer token"},
            )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_add_category_duplicate_returns_409(auth_app):
    with patch(
        "modules.settings.service.add_category",
        new=AsyncMock(side_effect=ValueError("Duplicate")),
    ):
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
            r = await c.post(
                "/categories/preferences",
                json={"category": "Alimentación", "category_type": "expense"},
                headers={"Authorization": "Bearer token"},
            )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_get_category_usage(auth_app):
    with patch(
        "modules.settings.service.get_category_usage",
        new=AsyncMock(return_value=7),
    ):
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
            r = await c.get(
                "/categories/preferences/Alimentaci%C3%B3n/usage",
                headers={"Authorization": "Bearer token"},
            )
    assert r.status_code == 200
    assert r.json()["count"] == 7


@pytest.mark.asyncio
async def test_post_delete_category(auth_app):
    with patch(
        "modules.settings.service.delete_category",
        new=AsyncMock(return_value=None),
    ):
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
            r = await c.post(
                "/categories/preferences/Hogar/delete",
                json={"reclassify_to": "Otros"},
                headers={"Authorization": "Bearer token"},
            )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_post_delete_invalid_reclassify_returns_422(auth_app):
    with patch(
        "modules.settings.service.delete_category",
        new=AsyncMock(side_effect=ValueError("not found")),
    ):
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
            r = await c.post(
                "/categories/preferences/Hogar/delete",
                json={"reclassify_to": "Nonexistent"},
                headers={"Authorization": "Bearer token"},
            )
    assert r.status_code == 422
