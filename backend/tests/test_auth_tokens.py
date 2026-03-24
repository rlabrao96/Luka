import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def mock_user_with_tokens():
    from modules.auth.models import User
    import uuid

    return User(
        id=uuid.uuid4(),
        email="rafa@test.cl",
        full_name="Rafa Test",
        email_provider="gmail",
        whatsapp_verified=False,
        google_access_token_enc=None,
        google_refresh_token_enc=None,
    )


@pytest.mark.asyncio
async def test_store_provider_tokens(app, mock_user_with_tokens):
    from core.security import get_current_user
    from core.database import get_db

    app.dependency_overrides[get_current_user] = lambda: mock_user_with_tokens

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_user_with_tokens)
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    async def _mock_db():
        yield mock_db

    app.dependency_overrides[get_db] = _mock_db

    with (
        patch("modules.auth.router.encrypt_token", side_effect=lambda x: f"enc_{x}"),
        patch("modules.auth.router.cache_delete", new_callable=AsyncMock),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            response = await c.post(
                "/auth/store-provider-tokens",
                json={
                    "provider_token": "google-access-tok",
                    "provider_refresh_token": "google-refresh-tok",
                },
            )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert mock_user_with_tokens.google_access_token_enc == "enc_google-access-tok"
    assert mock_user_with_tokens.google_refresh_token_enc == "enc_google-refresh-tok"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_store_provider_tokens_preserves_existing_refresh(app, mock_user_with_tokens):
    """When provider_refresh_token is None, existing refresh token should NOT be overwritten."""
    from core.security import get_current_user
    from core.database import get_db

    mock_user_with_tokens.google_refresh_token_enc = "enc_existing-refresh"
    app.dependency_overrides[get_current_user] = lambda: mock_user_with_tokens

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_user_with_tokens)
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    async def _mock_db():
        yield mock_db

    app.dependency_overrides[get_db] = _mock_db

    with (
        patch("modules.auth.router.encrypt_token", side_effect=lambda x: f"enc_{x}"),
        patch("modules.auth.router.cache_delete", new_callable=AsyncMock),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            response = await c.post(
                "/auth/store-provider-tokens",
                json={"provider_token": "new-access-tok"},
            )

    assert response.status_code == 200
    assert mock_user_with_tokens.google_refresh_token_enc == "enc_existing-refresh"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_setup_email_watch(app, mock_user_with_tokens):
    from core.security import get_current_user
    from core.database import get_db

    mock_user_with_tokens.google_access_token_enc = "enc_access"
    mock_user_with_tokens.google_refresh_token_enc = "enc_refresh"
    app.dependency_overrides[get_current_user] = lambda: mock_user_with_tokens

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_user_with_tokens)
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    async def _mock_db():
        yield mock_db

    app.dependency_overrides[get_db] = _mock_db

    mock_provider = AsyncMock()
    mock_provider.setup_watch = AsyncMock(
        return_value={"subscription_id": "history-123", "expiry": "1711234567890"}
    )
    mock_provider.get_current_token = MagicMock(return_value="refreshed-token")

    with (
        patch("modules.auth.router.decrypt_token", return_value="decrypted"),
        patch("modules.auth.router.encrypt_token", side_effect=lambda x: f"enc_{x}"),
        patch("modules.auth.router.get_email_provider", return_value=mock_provider),
        patch("modules.auth.router.cache_delete", new_callable=AsyncMock),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            response = await c.post("/auth/setup-email-watch")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert mock_user_with_tokens.mail_watch_subscription_id == "history-123"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_setup_email_watch_requires_tokens(app, mock_user_with_tokens):
    """Should return 400 if user has no stored Google tokens."""
    from core.security import get_current_user
    from core.database import get_db

    mock_user_with_tokens.google_access_token_enc = None
    app.dependency_overrides[get_current_user] = lambda: mock_user_with_tokens

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_user_with_tokens)
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def _mock_db():
        yield mock_db

    app.dependency_overrides[get_db] = _mock_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post("/auth/setup-email-watch")

    assert response.status_code == 400

    app.dependency_overrides.clear()
