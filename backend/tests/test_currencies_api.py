import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
from modules.auth.models import User


@pytest.fixture
def mock_user():
    return User(
        id=uuid.uuid4(),
        email="test@luka.cl",
        full_name="Test User",
        email_provider="gmail",
        whatsapp_verified=False,
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


def _fake_uc(code, is_primary=False, sort_order=0):
    m = MagicMock()
    m.currency_code = code
    m.is_primary = is_primary
    m.sort_order = sort_order
    return m


@pytest.mark.asyncio
async def test_get_currencies_returns_200(auth_app):
    rows = [_fake_uc("CLP", is_primary=True), _fake_uc("USD", sort_order=1)]
    with patch("modules.currencies.service.get_currencies", new=AsyncMock(return_value=rows)):
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
            r = await c.get("/currencies", headers={"Authorization": "Bearer token"})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert data[0]["currency_code"] == "CLP"
    assert data[0]["is_primary"] is True


@pytest.mark.asyncio
async def test_post_currencies_returns_201(auth_app):
    new_row = _fake_uc("USD", sort_order=1)
    with patch("modules.currencies.service.add_currency", new=AsyncMock(return_value=new_row)):
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
            r = await c.post(
                "/currencies",
                json={"currency_code": "USD"},
                headers={"Authorization": "Bearer token"},
            )
    assert r.status_code == 201
    assert r.json()["currency_code"] == "USD"


@pytest.mark.asyncio
async def test_post_currencies_invalid_code_returns_400(auth_app):
    with patch(
        "modules.currencies.service.add_currency",
        new=AsyncMock(side_effect=ValueError("Not supported: XXX")),
    ):
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
            r = await c.post(
                "/currencies",
                json={"currency_code": "XXX"},
                headers={"Authorization": "Bearer token"},
            )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_post_currencies_duplicate_returns_409(auth_app):
    with patch(
        "modules.currencies.service.add_currency",
        new=AsyncMock(side_effect=ValueError("Already in list: CLP")),
    ):
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
            r = await c.post(
                "/currencies",
                json={"currency_code": "CLP"},
                headers={"Authorization": "Bearer token"},
            )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_delete_currencies_returns_204(auth_app):
    with patch("modules.currencies.service.delete_currency", new=AsyncMock(return_value=None)):
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
            r = await c.delete(
                "/currencies/USD",
                headers={"Authorization": "Bearer token"},
            )
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_currencies_last_returns_400(auth_app):
    with patch(
        "modules.currencies.service.delete_currency",
        new=AsyncMock(side_effect=ValueError("Debes tener al menos una moneda activa")),
    ):
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
            r = await c.delete(
                "/currencies/CLP",
                headers={"Authorization": "Bearer token"},
            )
    assert r.status_code == 400
