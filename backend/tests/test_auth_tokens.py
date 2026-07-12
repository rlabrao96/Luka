"""Provider-token storage + email-watch setup endpoints.

Real DB (savepoint-rolled-back). The old AsyncMock-session versions rotted
when the endpoints moved to ``get_current_user_attached`` and gained the
Google tokeninfo ownership check — the mocks silently targeted the wrong
dependency and asserted on objects the endpoints never touched.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# Register models for FK resolution.
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401


@pytest.fixture
def wire(app, db):
    """Override auth + db for a REAL user row; returns a setup function."""
    from core.database import get_db
    from core.security import get_current_user, get_current_user_attached

    def _wire(user):
        async def _db():
            yield db

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_current_user_attached] = lambda: user
        app.dependency_overrides[get_db] = _db

    yield _wire
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_store_provider_tokens(app, db, make_user, wire):
    user = await make_user()
    wire(user)

    with (
        patch("modules.auth.router.encrypt_token", side_effect=lambda x: f"enc_{x}"),
        patch(
            "modules.auth.router._verify_google_token_ownership",
            new_callable=AsyncMock,
        ),
        patch("modules.auth.router.invalidate_user_cache", new_callable=AsyncMock),
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
    await db.refresh(user)
    assert user.google_access_token_enc == "enc_google-access-tok"
    assert user.google_refresh_token_enc == "enc_google-refresh-tok"


@pytest.mark.asyncio
async def test_store_provider_tokens_preserves_existing_refresh(app, db, make_user, wire):
    """When provider_refresh_token is None, the existing refresh token stays."""
    user = await make_user(google_refresh_token_enc="enc_existing-refresh")
    wire(user)

    with (
        patch("modules.auth.router.encrypt_token", side_effect=lambda x: f"enc_{x}"),
        patch(
            "modules.auth.router._verify_google_token_ownership",
            new_callable=AsyncMock,
        ),
        patch("modules.auth.router.invalidate_user_cache", new_callable=AsyncMock),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            response = await c.post(
                "/auth/store-provider-tokens",
                json={"provider_token": "new-access-tok"},
            )

    assert response.status_code == 200
    await db.refresh(user)
    assert user.google_refresh_token_enc == "enc_existing-refresh"


@pytest.mark.asyncio
async def test_setup_email_watch(app, db, make_user, wire):
    user = await make_user(
        google_access_token_enc="enc_access",
        google_refresh_token_enc="enc_refresh",
    )
    wire(user)

    mock_provider = AsyncMock()
    mock_provider.setup_watch = AsyncMock(
        return_value={"subscription_id": "history-123", "expiry": "1711234567890"}
    )
    mock_provider.get_current_token = MagicMock(return_value="refreshed-token")

    with (
        patch("modules.auth.router.decrypt_token", return_value="decrypted"),
        patch("modules.auth.router.encrypt_token", side_effect=lambda x: f"enc_{x}"),
        patch("modules.auth.router.get_email_provider", return_value=mock_provider),
        patch("modules.auth.router.invalidate_user_cache", new_callable=AsyncMock),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            response = await c.post("/auth/setup-email-watch")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    await db.refresh(user)
    assert user.mail_watch_subscription_id == "history-123"


@pytest.mark.asyncio
async def test_setup_email_watch_requires_tokens(app, db, make_user, wire):
    """400 when the user has no stored Google tokens."""
    user = await make_user(google_access_token_enc=None)
    wire(user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post("/auth/setup-email-watch")

    assert response.status_code == 400
