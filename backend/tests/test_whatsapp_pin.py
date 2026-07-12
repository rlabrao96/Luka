import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def mock_user_for_pin():
    from modules.auth.models import User
    import uuid

    return User(
        id=uuid.uuid4(),
        email="rafa@test.cl",
        full_name="Rafa Test",
        email_provider="gmail",
        whatsapp_verified=False,
        phone_whatsapp=None,
    )


@pytest.fixture
def setup_pin_app(app, mock_user_for_pin):
    from core.security import get_current_user
    from core.database import get_db

    app.dependency_overrides[get_current_user] = lambda: mock_user_for_pin

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_user_for_pin)
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    async def _mock_db():
        yield mock_db

    app.dependency_overrides[get_db] = _mock_db
    yield mock_db
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_send_pin_stores_in_redis_and_sends(app, mock_user_for_pin, setup_pin_app):
    with (
        patch("modules.auth.router.cache_get", new_callable=AsyncMock, return_value=None),
        patch("modules.auth.router.cache_set", new_callable=AsyncMock) as mock_cache_set,
        patch("modules.auth.router.send_verification_pin", new_callable=AsyncMock) as mock_send,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            response = await c.post("/auth/send-whatsapp-pin", json={"phone": "+56912345678"})

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    # Two writes: the rate-limit counter first, then the PIN itself.
    assert mock_cache_set.call_count == 2
    rl_args = mock_cache_set.call_args_list[0]
    assert rl_args[0][0].startswith("whatsapp_pin_rl:")
    call_args = mock_cache_set.call_args_list[-1]
    assert call_args[0][0] == "whatsapp_pin:+56912345678"
    stored = call_args[0][1]
    assert len(stored["pin"]) == 6
    assert stored["user_id"] == str(mock_user_for_pin.id)
    assert stored["attempts"] == 0
    assert call_args[1]["ttl_seconds"] == 300
    mock_send.assert_called_once_with("+56912345678", stored["pin"])


@pytest.mark.asyncio
async def test_send_pin_validates_phone_format(app, setup_pin_app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post("/auth/send-whatsapp-pin", json={"phone": "not-a-phone"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_verify_pin_success(app, mock_user_for_pin, setup_pin_app):
    pin_data = {"pin": "123456", "user_id": str(mock_user_for_pin.id), "attempts": 0}
    with (
        patch("modules.auth.router.cache_get", new_callable=AsyncMock, return_value=pin_data),
        patch("modules.auth.router.cache_delete", new_callable=AsyncMock) as mock_del,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            response = await c.post(
                "/auth/verify-whatsapp-pin", json={"phone": "+56912345678", "pin": "123456"}
            )

    assert response.status_code == 200
    assert mock_user_for_pin.phone_whatsapp == "+56912345678"
    assert mock_user_for_pin.whatsapp_verified is True
    assert mock_del.call_count == 2


@pytest.mark.asyncio
async def test_verify_pin_wrong_pin(app, mock_user_for_pin, setup_pin_app):
    pin_data = {"pin": "123456", "user_id": str(mock_user_for_pin.id), "attempts": 0}
    with (
        patch("modules.auth.router.cache_get", new_callable=AsyncMock, return_value=pin_data),
        patch("modules.auth.router.cache_set", new_callable=AsyncMock) as mock_set,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            response = await c.post(
                "/auth/verify-whatsapp-pin", json={"phone": "+56912345678", "pin": "999999"}
            )

    assert response.status_code == 400
    assert "incorrecto" in response.json()["detail"]
    mock_set.assert_called_once()
    stored = mock_set.call_args[0][1]
    assert stored["attempts"] == 1


@pytest.mark.asyncio
async def test_verify_pin_expired(app, setup_pin_app):
    with patch("modules.auth.router.cache_get", new_callable=AsyncMock, return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            response = await c.post(
                "/auth/verify-whatsapp-pin", json={"phone": "+56912345678", "pin": "123456"}
            )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_verify_pin_wrong_user(app, setup_pin_app):
    pin_data = {"pin": "123456", "user_id": "00000000-0000-0000-0000-000000000000", "attempts": 0}
    with patch("modules.auth.router.cache_get", new_callable=AsyncMock, return_value=pin_data):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            response = await c.post(
                "/auth/verify-whatsapp-pin", json={"phone": "+56912345678", "pin": "123456"}
            )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_verify_pin_lockout_after_5_attempts(app, mock_user_for_pin, setup_pin_app):
    pin_data = {"pin": "123456", "user_id": str(mock_user_for_pin.id), "attempts": 4}
    with (
        patch("modules.auth.router.cache_get", new_callable=AsyncMock, return_value=pin_data),
        patch("modules.auth.router.cache_delete", new_callable=AsyncMock) as mock_del,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            response = await c.post(
                "/auth/verify-whatsapp-pin", json={"phone": "+56912345678", "pin": "999999"}
            )
    assert response.status_code == 400
    mock_del.assert_called_once_with("whatsapp_pin:+56912345678")
