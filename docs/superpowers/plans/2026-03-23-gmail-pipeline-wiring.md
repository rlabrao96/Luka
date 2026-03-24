# Gmail Pipeline Wiring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the existing email-to-WhatsApp transaction pipeline to work end-to-end with Gmail by adding token storage, token capture, Gmail watch setup, and fixing all placeholder values.

**Architecture:** Fernet-encrypted Google OAuth tokens stored on the `users` table, captured from Supabase OAuth callback, decrypted at runtime by ARQ jobs (`process_email`, `renew_mail_watches`). `GmailProvider` updated with `client_id`/`client_secret` for auto-refresh and `asyncio.to_thread()` for non-blocking calls. Two new auth endpoints: `store-provider-tokens` and `setup-email-watch`.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, ARQ, cryptography (Fernet), google-auth, google-api-python-client, Next.js 14

**Spec:** `docs/superpowers/specs/2026-03-23-gmail-pipeline-wiring-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `backend/core/encryption.py` | **New** — Fernet encrypt/decrypt with singleton instance |
| `backend/core/config.py` | Add `token_encryption_key`, `google_client_id`, `google_client_secret`, `gmail_pubsub_topic` |
| `backend/modules/auth/models.py` | Add `google_access_token_enc`, `google_refresh_token_enc` columns |
| `backend/modules/auth/schemas.py` | Add `StoreProviderTokensRequest` schema |
| `backend/modules/auth/router.py` | Add `POST /auth/store-provider-tokens`, `POST /auth/setup-email-watch` |
| `backend/modules/email/gmail.py` | Pass OAuth client creds, configurable topic, `asyncio.to_thread()`, `get_current_token()` |
| `backend/jobs/tasks.py` | Wire real tokens + real phone in `process_email` and `renew_mail_watches` |
| `backend/alembic/versions/016_google_token_columns.py` | **New** — migration for token columns |
| `backend/pyproject.toml` | Add `cryptography` dependency |
| `frontend/app/auth/callback/route.ts` | Capture + send provider tokens to backend |
| `backend/tests/test_encryption.py` | **New** — encryption round-trip tests |
| `backend/tests/test_auth_tokens.py` | **New** — store-provider-tokens + setup-email-watch endpoint tests |

---

### Task 1: Add `cryptography` Dependency

**Files:**
- Modify: `backend/pyproject.toml:5-25`

- [ ] **Step 1: Add cryptography to dependencies**

In `backend/pyproject.toml`, add `"cryptography>=43.0"` and `"google-api-python-client>=2.0"` to the `dependencies` list, after `"pydantic[email]>=2.12.5"`:

```python
    "pydantic[email]>=2.12.5",
    "cryptography>=43.0",
    "google-api-python-client>=2.0",
```

Note: `google-api-python-client` provides `googleapiclient.discovery.build` used by `GmailProvider`. It was not previously listed despite being imported.

- [ ] **Step 2: Install**

Run: `cd backend && pip install -e ".[dev]"`
Expected: cryptography installs successfully

- [ ] **Step 3: Commit**

```bash
git add backend/pyproject.toml
git commit -m "chore: add cryptography dependency for token encryption"
```

---

### Task 2: Encryption Helper

**Files:**
- Create: `backend/core/encryption.py`
- Test: `backend/tests/test_encryption.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_encryption.py`:

```python
import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def reset_fernet():
    """Reset singleton between tests."""
    import core.encryption as enc
    enc._fernet = None
    yield
    enc._fernet = None


def test_encrypt_decrypt_round_trip():
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    with patch("core.encryption.settings") as mock_settings:
        mock_settings.token_encryption_key = key
        from core.encryption import encrypt_token, decrypt_token

        ciphertext = encrypt_token("my-secret-token")
        assert ciphertext != "my-secret-token"
        assert decrypt_token(ciphertext) == "my-secret-token"


def test_decrypt_with_wrong_key_raises():
    from cryptography.fernet import Fernet, InvalidToken

    key1 = Fernet.generate_key().decode()
    key2 = Fernet.generate_key().decode()

    with patch("core.encryption.settings") as mock_settings:
        mock_settings.token_encryption_key = key1
        from core.encryption import encrypt_token

        ciphertext = encrypt_token("secret")

    import core.encryption as enc
    enc._fernet = None

    with patch("core.encryption.settings") as mock_settings:
        mock_settings.token_encryption_key = key2
        from core.encryption import decrypt_token

        with pytest.raises(InvalidToken):
            decrypt_token(ciphertext)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_encryption.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.encryption'`

- [ ] **Step 3: Write implementation**

Create `backend/core/encryption.py`:

```python
from cryptography.fernet import Fernet
from core.config import settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(settings.token_encryption_key.encode())
    return _fernet


def encrypt_token(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_encryption.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/core/encryption.py backend/tests/test_encryption.py
git commit -m "feat: add Fernet encryption helper for token storage"
```

---

### Task 3: Config Settings

**Files:**
- Modify: `backend/core/config.py:4-28`

- [ ] **Step 1: Add settings**

In `backend/core/config.py`, add these four lines after `gcp_project_id` (line 27):

```python
    gmail_pubsub_topic: str = "luka-gmail-notifications"
    google_client_id: str = ""
    google_client_secret: str = ""
    token_encryption_key: str = ""
```

- [ ] **Step 2: Verify import works**

Run: `cd backend && python -c "from core.config import settings; print(settings.gmail_pubsub_topic)"`
Expected: `luka-gmail-notifications`

- [ ] **Step 3: Commit**

```bash
git add backend/core/config.py
git commit -m "feat: add Google OAuth and encryption config settings"
```

---

### Task 4: User Model — Token Columns

**Files:**
- Modify: `backend/modules/auth/models.py:9-25`

- [ ] **Step 1: Add columns to User model**

In `backend/modules/auth/models.py`, add these two lines after `mail_watch_expiry` (line 20):

```python
    google_access_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_refresh_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Also add `Text` to the SQLAlchemy imports at the top of the file:

```python
from sqlalchemy import Boolean, DateTime, String, Text, func
```

- [ ] **Step 2: Verify model loads**

Run: `cd backend && python -c "from modules.auth.models import User; print([c.name for c in User.__table__.columns])"`
Expected: list includes `google_access_token_enc` and `google_refresh_token_enc`

- [ ] **Step 3: Commit**

```bash
git add backend/modules/auth/models.py
git commit -m "feat: add encrypted Google token columns to User model"
```

---

### Task 5: Alembic Migration

**Files:**
- Create: `backend/alembic/versions/016_google_token_columns.py`

- [ ] **Step 1: Create migration**

Create `backend/alembic/versions/016_google_token_columns.py`:

```python
"""Add encrypted Google OAuth token columns to users.

Revision ID: 016
Revises: 015
"""

import sqlalchemy as sa
from alembic import op

revision = "016"
down_revision = "015"


def upgrade() -> None:
    op.add_column("users", sa.Column("google_access_token_enc", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("google_refresh_token_enc", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "google_refresh_token_enc")
    op.drop_column("users", "google_access_token_enc")
```

- [ ] **Step 2: Verify migration chain**

Run: `cd backend && python -m alembic heads`
Expected: shows `016 (head)`

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/016_google_token_columns.py
git commit -m "feat: migration 016 — add Google token columns to users"
```

---

### Task 6: Auth Schema + Store Provider Tokens Endpoint

**Files:**
- Modify: `backend/modules/auth/schemas.py:1-24`
- Modify: `backend/modules/auth/router.py:1-92`
- Test: `backend/tests/test_auth_tokens.py`

- [ ] **Step 1: Add request schema**

In `backend/modules/auth/schemas.py`, add after `UpdateProfileRequest` (line 24):

```python
class StoreProviderTokensRequest(BaseModel):
    provider_token: str
    provider_refresh_token: str | None = None
```

- [ ] **Step 2: Write failing test for store-provider-tokens**

Create `backend/tests/test_auth_tokens.py`:

```python
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
    mock_result.scalar_one = MagicMock(return_value=mock_user_with_tokens)
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
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
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
    mock_result.scalar_one = MagicMock(return_value=mock_user_with_tokens)
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
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            response = await c.post(
                "/auth/store-provider-tokens",
                json={"provider_token": "new-access-tok"},
            )

    assert response.status_code == 200
    # Refresh token should be preserved (not overwritten with None)
    assert mock_user_with_tokens.google_refresh_token_enc == "enc_existing-refresh"

    app.dependency_overrides.clear()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_auth_tokens.py -v`
Expected: FAIL — 404 (endpoint doesn't exist yet)

- [ ] **Step 4: Implement the endpoint**

In `backend/modules/auth/router.py`, add these imports at the top:

```python
from core.cache import cache_delete
from core.encryption import encrypt_token
from modules.auth.schemas import StoreProviderTokensRequest, UpdateProfileRequest, UserResponse
```

And update the existing import line to remove `UpdateProfileRequest, UserResponse` from `modules.auth.schemas` (they'll be in the combined import above).

Then add this endpoint after the `delete_account` endpoint:

```python
@router.post("/store-provider-tokens")
async def store_provider_tokens(
    body: StoreProviderTokensRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Re-fetch user from DB session (current_user may be cached/detached)
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()

    user.google_access_token_enc = encrypt_token(body.provider_token)
    if body.provider_refresh_token is not None:
        user.google_refresh_token_enc = encrypt_token(body.provider_refresh_token)

    await db.commit()
    await db.refresh(user)
    await cache_delete(f"user:{user.email}")

    return {"status": "ok"}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_auth_tokens.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add backend/modules/auth/schemas.py backend/modules/auth/router.py backend/tests/test_auth_tokens.py
git commit -m "feat: POST /auth/store-provider-tokens endpoint with encryption"
```

---

### Task 7: Setup Email Watch Endpoint

**Files:**
- Modify: `backend/modules/auth/router.py`
- Modify: `backend/tests/test_auth_tokens.py`

- [ ] **Step 1: Write failing test**

Add to `backend/tests/test_auth_tokens.py`:

```python
@pytest.mark.asyncio
async def test_setup_email_watch(app, mock_user_with_tokens):
    from core.security import get_current_user
    from core.database import get_db

    mock_user_with_tokens.google_access_token_enc = "enc_access"
    mock_user_with_tokens.google_refresh_token_enc = "enc_refresh"
    app.dependency_overrides[get_current_user] = lambda: mock_user_with_tokens

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one = MagicMock(return_value=mock_user_with_tokens)
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
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
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
    mock_result.scalar_one = MagicMock(return_value=mock_user_with_tokens)
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def _mock_db():
        yield mock_db

    app.dependency_overrides[get_db] = _mock_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        response = await c.post("/auth/setup-email-watch")

    assert response.status_code == 400

    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_auth_tokens.py::test_setup_email_watch -v`
Expected: FAIL — 404

- [ ] **Step 3: Implement the endpoint**

Add these imports to `backend/modules/auth/router.py`:

```python
from datetime import datetime, timezone
from core.encryption import decrypt_token
from modules.email.factory import get_email_provider
```

Then add the endpoint:

```python
@router.post("/setup-email-watch")
async def setup_email_watch(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()

    if not user.google_access_token_enc:
        raise HTTPException(status_code=400, detail="No Google tokens stored. Please re-authenticate.")

    access_token = decrypt_token(user.google_access_token_enc)
    refresh_token = (
        decrypt_token(user.google_refresh_token_enc) if user.google_refresh_token_enc else ""
    )

    provider = get_email_provider(user, access_token=access_token, refresh_token=refresh_token)
    watch_result = await provider.setup_watch(str(user.id))

    user.mail_watch_subscription_id = watch_result.get("subscription_id")
    expiry_ms = watch_result.get("expiry")
    if expiry_ms:
        user.mail_watch_expiry = datetime.fromtimestamp(int(expiry_ms) / 1000, tz=timezone.utc)

    # Persist refreshed token if changed
    new_token = provider.get_current_token()
    if new_token and new_token != access_token:
        user.google_access_token_enc = encrypt_token(new_token)

    await db.commit()
    await db.refresh(user)
    await cache_delete(f"user:{user.email}")

    return {
        "status": "ok",
        "expiry": str(user.mail_watch_expiry) if user.mail_watch_expiry else None,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_auth_tokens.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/modules/auth/router.py backend/tests/test_auth_tokens.py
git commit -m "feat: POST /auth/setup-email-watch endpoint"
```

---

### Task 8: Update GmailProvider

**Files:**
- Modify: `backend/modules/email/gmail.py:1-78`

- [ ] **Step 1: Update `_build_service()` with client credentials**

Replace the entire content of `backend/modules/email/gmail.py` with:

```python
import asyncio
import base64
from datetime import datetime, timezone

from modules.email.base import EmailProvider, RawEmail


class GmailProvider(EmailProvider):
    def __init__(self, access_token: str, refresh_token: str):
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._creds = None

    def _build_service(self):
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        from core.config import settings

        self._creds = Credentials(
            token=self._access_token,
            refresh_token=self._refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
        )
        return build("gmail", "v1", credentials=self._creds, cache_discovery=False)

    def get_current_token(self) -> str | None:
        """Return the current access token (may have been refreshed by the SDK)."""
        return self._creds.token if self._creds else None

    async def setup_watch(self, user_id: str) -> dict:
        from core.config import settings

        service = self._build_service()
        body = {
            "topicName": f"projects/{settings.gcp_project_id}/topics/{settings.gmail_pubsub_topic}",
            "labelIds": ["INBOX"],
        }
        result = await asyncio.to_thread(
            service.users().watch(userId="me", body=body).execute
        )
        return {
            "subscription_id": result.get("historyId"),
            "expiry": result.get("expiration"),
        }

    async def fetch_new_emails(self, user_id: str, history_id: str = None, **kwargs) -> list[RawEmail]:
        service = self._build_service()
        if not history_id:
            return []

        history = await asyncio.to_thread(
            service.users()
            .history()
            .list(userId="me", startHistoryId=history_id, historyTypes=["messageAdded"])
            .execute
        )

        emails = []
        for record in history.get("history", []):
            for msg_ref in record.get("messagesAdded", []):
                msg = await asyncio.to_thread(
                    service.users()
                    .messages()
                    .get(userId="me", id=msg_ref["message"]["id"], format="full")
                    .execute
                )
                emails.append(self._parse_gmail_message(msg))
        return emails

    def _parse_gmail_message(self, msg: dict) -> RawEmail:
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        body = ""
        if "data" in msg["payload"].get("body", {}):
            body = base64.urlsafe_b64decode(msg["payload"]["body"]["data"]).decode(
                "utf-8", errors="ignore"
            )
        return RawEmail(
            message_id=msg["id"],
            subject=headers.get("Subject", ""),
            sender=headers.get("From", ""),
            body=body,
            received_at=datetime.now(timezone.utc),
        )

    async def renew_watch(self, user_id: str) -> dict:
        """Renew watch — returns same dict as setup_watch (subscription_id, expiry)."""
        return await self.setup_watch(user_id)
```

Note: `renew_watch` now returns a dict instead of None, so callers can persist the updated expiry. The base class `EmailProvider` abstract method should also be updated to return `dict` (change `async def renew_watch(self, user_id: str) -> None` to `-> dict` in `base.py`).

- [ ] **Step 2: Run existing tests to verify nothing broke**

Run: `cd backend && python -m pytest tests/test_email_webhooks.py tests/test_email_parser.py -v`
Expected: All existing tests pass

- [ ] **Step 3: Commit**

```bash
git add backend/modules/email/gmail.py
git commit -m "feat: update GmailProvider with client creds, async wrapping, configurable topic"
```

---

### Task 9: Wire Real Tokens in `process_email`

**Files:**
- Modify: `backend/jobs/tasks.py:120-237`

- [ ] **Step 1: Add import**

At the top of `backend/jobs/tasks.py` (after the existing imports around line 9), add:

```python
from core.encryption import decrypt_token, encrypt_token
```

- [ ] **Step 2: Replace placeholder tokens in `process_email`**

In `backend/jobs/tasks.py`, replace lines 152-155 (the comment and placeholder):

```python
        # Access token retrieved from Supabase Vault in production
        # For now, use a placeholder — Vault integration added in Plan 3
        provider_instance = get_email_provider(user, access_token="", refresh_token="")
```

with:

```python
        if not user.google_access_token_enc:
            logger.warning("process_email: user %s has no Google tokens stored", user.email)
            return

        try:
            access_token = decrypt_token(user.google_access_token_enc)
            refresh_token = (
                decrypt_token(user.google_refresh_token_enc)
                if user.google_refresh_token_enc
                else ""
            )
        except Exception as e:
            logger.error("process_email: failed to decrypt tokens for %s: %s", user.email, e)
            return

        provider_instance = get_email_provider(
            user, access_token=access_token, refresh_token=refresh_token
        )
```

- [ ] **Step 3: Add token refresh persistence after fetch_new_emails**

After the `emails = await provider_instance.fetch_new_emails(...)` call (around line 158), add:

```python
        # Persist refreshed token if the SDK auto-refreshed
        new_token = provider_instance.get_current_token()
        if new_token and new_token != access_token:
            user.google_access_token_enc = encrypt_token(new_token)
            await db.commit()
```

- [ ] **Step 4: Replace hardcoded phone number**

Replace the hardcoded phone block (lines 212-214):

```python
                # Retrieve phone from Supabase Vault (placeholder)
                phone = "+56900000000"  # TODO: retrieve from Vault in Plan 3
```

with:

```python
                phone = user.phone_whatsapp
                if not phone:
                    logger.info("process_email: user %s has no phone, skipping WhatsApp", user.email)
                    continue
```

- [ ] **Step 5: Add RefreshError handling**

Wrap the `provider_instance.fetch_new_emails()` call with a try/except for `google.auth.exceptions.RefreshError`. After the `provider_instance = get_email_provider(...)` line:

```python
        try:
            emails = await provider_instance.fetch_new_emails(
                str(user.id), history_id=history_id, message_id=message_id
            )
        except Exception as e:
            if "RefreshError" in type(e).__name__ or "invalid_grant" in str(e).lower():
                logger.warning(
                    "process_email: Google token revoked for %s, clearing tokens", user.email
                )
                user.google_access_token_enc = None
                user.google_refresh_token_enc = None
                await db.commit()
                return
            raise
```

(Remove the old `emails = await provider_instance.fetch_new_emails(...)` line that this replaces.)

- [ ] **Step 6: Run existing tests**

Run: `cd backend && python -m pytest tests/ -v --timeout=30`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add backend/jobs/tasks.py
git commit -m "feat: wire real tokens and phone in process_email job"
```

---

### Task 10: Tests for `process_email` Token Wiring

**Files:**
- Create: `backend/tests/test_process_email_tokens.py`

- [ ] **Step 1: Write tests**

Create `backend/tests/test_process_email_tokens.py`:

```python
import pytest
import uuid
from unittest.mock import patch, AsyncMock, MagicMock
from modules.auth.models import User


@pytest.fixture
def user_no_tokens():
    return User(
        id=uuid.uuid4(),
        email="rafa@test.cl",
        full_name="Rafa Test",
        email_provider="gmail",
        whatsapp_verified=True,
        phone_whatsapp="+56912345678",
        google_access_token_enc=None,
        google_refresh_token_enc=None,
    )


@pytest.fixture
def user_with_tokens():
    return User(
        id=uuid.uuid4(),
        email="rafa@test.cl",
        full_name="Rafa Test",
        email_provider="gmail",
        whatsapp_verified=True,
        phone_whatsapp="+56912345678",
        google_access_token_enc="enc_access",
        google_refresh_token_enc="enc_refresh",
    )


@pytest.fixture
def user_no_phone():
    return User(
        id=uuid.uuid4(),
        email="rafa@test.cl",
        full_name="Rafa Test",
        email_provider="gmail",
        whatsapp_verified=True,
        phone_whatsapp=None,
        google_access_token_enc="enc_access",
        google_refresh_token_enc="enc_refresh",
    )


@pytest.mark.asyncio
async def test_process_email_skips_when_no_tokens(user_no_tokens):
    """process_email should return early if user has no Google tokens."""
    from jobs.tasks import process_email

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=user_no_tokens)
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("jobs.tasks.AsyncSessionLocal") as mock_session_cls:
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        # Should not raise, just return early
        await process_email(
            ctx={},
            provider="gmail",
            email_address="rafa@test.cl",
            history_id="123",
        )


@pytest.mark.asyncio
async def test_process_email_clears_tokens_on_refresh_error(user_with_tokens):
    """process_email should null tokens when Google returns RefreshError."""
    from jobs.tasks import process_email

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=user_with_tokens)
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    mock_provider = AsyncMock()
    mock_provider.fetch_new_emails = AsyncMock(
        side_effect=Exception("invalid_grant: Token has been revoked")
    )

    with (
        patch("jobs.tasks.AsyncSessionLocal") as mock_session_cls,
        patch("jobs.tasks.decrypt_token", return_value="decrypted"),
        patch("jobs.tasks.get_email_provider", return_value=mock_provider),
    ):
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await process_email(
            ctx={},
            provider="gmail",
            email_address="rafa@test.cl",
            history_id="123",
        )

    assert user_with_tokens.google_access_token_enc is None
    assert user_with_tokens.google_refresh_token_enc is None
```

- [ ] **Step 2: Run tests**

Run: `cd backend && python -m pytest tests/test_process_email_tokens.py -v`
Expected: 2 passed

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_process_email_tokens.py
git commit -m "test: add process_email token wiring tests"
```

---

### Task 11: Wire Real Tokens in `renew_mail_watches`


**Files:**
- Modify: `backend/jobs/tasks.py:240-260`

- [ ] **Step 1: Update renew_mail_watches**

Replace the body of `renew_mail_watches` (lines 241-259) with:

```python
async def renew_mail_watches(ctx: dict) -> None:
    """Daily job: renew Gmail (7d) and Outlook (~3d) subscriptions."""
    async with AsyncSessionLocal() as db:
        cutoff = datetime.now(timezone.utc) + timedelta(hours=24)
        result = await db.execute(
            select(User).where(
                and_(User.mail_watch_expiry.isnot(None), User.mail_watch_expiry <= cutoff)
            )
        )
        users = result.scalars().all()
        for user in users:
            if not user.google_access_token_enc:
                logger.warning("renew_mail_watches: user %s has no tokens, skipping", user.email)
                continue
            try:
                from modules.email.factory import get_email_provider

                access_token = decrypt_token(user.google_access_token_enc)
                refresh_token = (
                    decrypt_token(user.google_refresh_token_enc)
                    if user.google_refresh_token_enc
                    else ""
                )
                provider = get_email_provider(
                    user, access_token=access_token, refresh_token=refresh_token
                )
                watch_result = await provider.renew_watch(str(user.id))

                # Persist updated expiry from renewed watch
                user.mail_watch_subscription_id = watch_result.get("subscription_id")
                expiry_ms = watch_result.get("expiry")
                if expiry_ms:
                    user.mail_watch_expiry = datetime.fromtimestamp(
                        int(expiry_ms) / 1000, tz=timezone.utc
                    )

                # Persist refreshed token if changed
                new_token = provider.get_current_token()
                if new_token and new_token != access_token:
                    user.google_access_token_enc = encrypt_token(new_token)

                await db.commit()
            except Exception as e:
                if "RefreshError" in type(e).__name__ or "invalid_grant" in str(e).lower():
                    logger.warning(
                        "renew_mail_watches: Google token revoked for %s", user.email
                    )
                    user.google_access_token_enc = None
                    user.google_refresh_token_enc = None
                    await db.commit()
                    continue
                await _record_failed_job(
                    "renew_mail_watches", {"user_id": str(user.id)}, str(e), db
                )
```

- [ ] **Step 2: Run tests**

Run: `cd backend && python -m pytest tests/ -v --timeout=30`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add backend/jobs/tasks.py
git commit -m "feat: wire real tokens in renew_mail_watches job"
```

---

### Task 12: Frontend — Capture Provider Tokens in OAuth Callback

**Files:**
- Modify: `frontend/app/auth/callback/route.ts:1-36`

- [ ] **Step 1: Update callback to capture and send tokens**

Replace the entire content of `frontend/app/auth/callback/route.ts` with:

```typescript
import { createClient } from "@/app/lib/supabase/server";
import { NextResponse } from "next/server";

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");

  if (code) {
    const supabase = await createClient();
    const { data } = await supabase.auth.exchangeCodeForSession(code);
    const session = data?.session;

    if (session) {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

      // Store Google provider tokens for Gmail API access
      if (session.provider_token) {
        try {
          await fetch(`${apiUrl}/auth/store-provider-tokens`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${session.access_token}`,
            },
            body: JSON.stringify({
              provider_token: session.provider_token,
              provider_refresh_token: session.provider_refresh_token ?? null,
            }),
          });
        } catch (err) {
          console.error("Failed to store provider tokens", err);
        }
      }

      // Check if user needs onboarding
      try {
        const res = await fetch(`${apiUrl}/auth/me`, {
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${session.access_token}`,
          },
        });
        if (res.ok) {
          const user = await res.json();
          if (!user.household_id) {
            return NextResponse.redirect(`${origin}/onboarding/setup-household`);
          }
        }
      } catch (err) {
        console.error("Failed to fetch user during callback", err);
      }
    }
  }

  // Fallback or returning user
  return NextResponse.redirect(`${origin}/`);
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx next build --no-lint 2>&1 | tail -5`
Expected: Build succeeds (or at least no errors in `auth/callback/route.ts`)

- [ ] **Step 3: Commit**

```bash
git add frontend/app/auth/callback/route.ts
git commit -m "feat: capture Google provider tokens in OAuth callback"
```

---

### Task 13: Run Full Test Suite

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && python -m pytest tests/ -v --timeout=30`
Expected: All tests pass (no regressions)

- [ ] **Step 2: Run frontend build check**

Run: `cd frontend && npx next build --no-lint 2>&1 | tail -10`
Expected: Build succeeds

- [ ] **Step 3: Final commit if any formatting fixes needed**

Run: `cd backend && ruff check --fix . && ruff format .`
If files changed:
```bash
git add -u
git commit -m "style: auto-format with ruff"
```
