# Gmail Email Pipeline Wiring — Design Spec
**Date:** 2026-03-23
**Status:** Approved
**Scope:** Wire the existing email-to-WhatsApp pipeline to work end-to-end with Gmail, including token storage, GCP Pub/Sub setup, and watch management.

---

## Context

The email scraping pipeline (email webhook → ARQ job → parse → merchant lookup → WhatsApp alert) is fully coded but has never run end-to-end because:

1. No mechanism to store/retrieve the user's Google OAuth tokens for Gmail API calls
2. GCP Pub/Sub topic and push subscription not configured
3. `process_email` and `renew_mail_watches` jobs pass empty placeholder tokens
4. No endpoint to trigger the initial Gmail watch setup
5. `GmailProvider` doesn't pass `client_id`/`client_secret` to Google SDK (needed for token refresh)
6. WhatsApp phone number is hardcoded

**Out of scope:** Outlook/Azure, Supabase Vault, WhatsApp PIN verification.

---

## 1. Token Storage

### 1.1 Encryption Helper — `core/encryption.py` (new file)

```python
from cryptography.fernet import Fernet
from core.config import settings

# Singleton Fernet instance — avoids re-creating on every call
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

### 1.2 Config — `core/config.py`

Add four new settings:

```python
token_encryption_key: str = ""    # Fernet key (generate with Fernet.generate_key())
google_client_id: str = ""        # GCP OAuth client ID
google_client_secret: str = ""    # GCP OAuth client secret
gmail_pubsub_topic: str = "luka-gmail-notifications"  # Pub/Sub topic name (must match GCP Console)
```

### 1.3 User Model — `modules/auth/models.py`

Add two nullable columns:

```python
google_access_token_enc: Mapped[str | None] = mapped_column(String, nullable=True)
google_refresh_token_enc: Mapped[str | None] = mapped_column(String, nullable=True)
```

### 1.4 Alembic Migration 013

Add `google_access_token_enc` and `google_refresh_token_enc` (both `Text, nullable=True`) to the `users` table.

---

## 2. Token Capture Flow

### 2.1 Frontend — `frontend/app/auth/callback/route.ts`

**Critical:** Use the return value from `exchangeCodeForSession` directly — not a subsequent `getSession()` call. Supabase only exposes `provider_token` and `provider_refresh_token` on the initial exchange response; they may not persist in the stored session.

```typescript
const { data } = await supabase.auth.exchangeCodeForSession(code);
const session = data?.session;

if (session?.provider_token) {
  try {
    await fetch(`${apiUrl}/auth/store-provider-tokens`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${session.access_token}`,
      },
      body: JSON.stringify({
        provider_token: session.provider_token,
        provider_refresh_token: session.provider_refresh_token ?? null,
      }),
    });
  } catch (err) {
    console.error("Failed to store provider tokens", err);
    // Non-blocking: user can still log in. Settings page will show
    // "Gmail not connected" and they can re-authenticate to fix.
  }
}
```

**Error handling:** If token storage fails, the user still logs in successfully. The settings page should show a "Gmail connected" status indicator (checking if `google_access_token_enc` is set on the user). If not connected, the user can re-trigger OAuth to retry.

### 2.2 Backend — `POST /auth/store-provider-tokens`

Request schema:

```python
class StoreProviderTokensRequest(BaseModel):
    provider_token: str
    provider_refresh_token: str | None = None
```

Behavior:
- Requires Supabase JWT auth
- Encrypts `provider_token` with Fernet → stores as `google_access_token_enc`
- Encrypts `provider_refresh_token` with Fernet → stores as `google_refresh_token_enc`
- **Only overwrites `refresh_token` if a new one is provided** (Supabase only returns it on first consent)
- Invalidates Redis user cache (`user:{email}`)
- Returns `200 {"status": "ok"}`

---

## 3. Token Usage in Pipeline

### 3.1 `process_email` job — `jobs/tasks.py`

Replace placeholder tokens (line 155):

```python
from core.encryption import decrypt_token

access_token = decrypt_token(user.google_access_token_enc) if user.google_access_token_enc else ""
refresh_token = decrypt_token(user.google_refresh_token_enc) if user.google_refresh_token_enc else ""
provider_instance = get_email_provider(user, access_token=access_token, refresh_token=refresh_token)
```

Replace hardcoded phone (line 213):

```python
phone = user.phone_whatsapp
if not phone:
    continue  # can't send WhatsApp without phone number
```

### 3.2 `renew_mail_watches` job — `jobs/tasks.py`

Same decrypt pattern as `process_email`:

```python
from core.encryption import decrypt_token

access_token = decrypt_token(user.google_access_token_enc) if user.google_access_token_enc else ""
refresh_token = decrypt_token(user.google_refresh_token_enc) if user.google_refresh_token_enc else ""
provider = get_email_provider(user, access_token=access_token, refresh_token=refresh_token)
await provider.renew_watch(str(user.id))
```

### 3.3 `GmailProvider._build_service()` — `modules/email/gmail.py`

Pass `client_id` and `client_secret` to `Credentials` so the Google SDK can auto-refresh expired access tokens:

```python
from core.config import settings

creds = Credentials(
    token=self._access_token,
    refresh_token=self._refresh_token,
    token_uri="https://oauth2.googleapis.com/token",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
)
```

**Topic name from config:** Update `setup_watch()` to use `settings.gmail_pubsub_topic` instead of the hardcoded `luka-gmail` string:

```python
"topicName": f"projects/{settings.gcp_project_id}/topics/{settings.gmail_pubsub_topic}",
```

**Sync API in async context:** The Google API client (`googleapiclient`) is synchronous and blocks the event loop. Wrap all `.execute()` calls in `asyncio.to_thread()`:

```python
import asyncio

result = await asyncio.to_thread(
    service.users().watch(userId="me", body={...}).execute
)
```

This applies to `setup_watch()`, `fetch_new_emails()`, and `renew_watch()`.

### 3.4 Persist Refreshed Tokens

After `GmailProvider` makes an API call, the Google SDK may have refreshed the access token in-memory. We need to persist it:

- Add a method to `GmailProvider`: `get_current_token() → str` that returns `creds.token`
- After `fetch_new_emails()` and `setup_watch()` calls in `process_email` and `renew_mail_watches`, check if the token changed and update the DB if so
- This keeps the stored token fresh, avoiding unnecessary refresh round-trips

**Handling revoked tokens:** If the user revokes Google access or the refresh token becomes invalid, the Google SDK raises `google.auth.exceptions.RefreshError`. When caught:
1. Null out `google_access_token_enc` and `google_refresh_token_enc` on the user row
2. Log a warning
3. The settings page "Gmail connected" status will show disconnected, prompting re-authentication

---

## 4. Gmail Watch Setup

### 4.1 New Endpoint — `POST /auth/setup-email-watch`

- Requires Supabase JWT auth
- Decrypts user's Google tokens
- Creates `GmailProvider` and calls `setup_watch()`
- Stores returned `historyId` → `user.mail_watch_subscription_id`
- Stores returned `expiration` → `user.mail_watch_expiry` (as datetime)
- Invalidates Redis user cache
- Returns `200 {"status": "ok", "expiry": "..."}`

### 4.2 Frontend Trigger

Call `POST /auth/setup-email-watch` at the end of the onboarding flow (after bank account connected). Could also be triggered from settings page to re-enable email watching.

### 4.3 Watch Renewal

Already handled by `renew_mail_watches` ARQ cron (daily at 3 AM, 7-day Gmail expiry). Only change: wire real tokens (Section 3.2).

---

## 5. OAuth Scopes

### 5.1 GCP Console — OAuth Consent Screen

Add scope: `https://www.googleapis.com/auth/gmail.readonly`

This appears on the Google consent screen when the user logs in — "Luka wants to view your email messages and settings."

### 5.2 Supabase Dashboard — Auth → Google Provider

In the Google provider configuration, add `gmail.readonly` to the "Additional scopes" field (comma or space-separated, depends on Supabase UI version).

---

## 6. GCP Console Setup Guide (Manual Steps)

### Step 1: Enable APIs

1. Go to [GCP Console → APIs & Services → Library](https://console.cloud.google.com/apis/library)
2. Search and enable: **Gmail API**
3. Search and enable: **Cloud Pub/Sub API**

### Step 2: Create Pub/Sub Topic

1. Go to [Pub/Sub → Topics](https://console.cloud.google.com/cloudpubsub/topic/list)
2. Click **Create Topic**
3. Topic ID: `luka-gmail-notifications`
4. Leave defaults, click **Create**

### Step 3: Grant Gmail Publish Permission

1. Click on the newly created topic → **Permissions** tab
2. Click **Add Principal**
3. Principal: `gmail-api-push@system.gserviceaccount.com`
4. Role: **Pub/Sub Publisher**
5. Click **Save**

### Step 4: Create Push Subscription

1. Click on the topic → **Subscriptions** tab → **Create Subscription**
2. Subscription ID: `luka-gmail-push`
3. Delivery type: **Push**
4. Endpoint URL: `https://luka-production-eb87.up.railway.app/webhooks/gmail`
5. Enable authentication: **Yes**
   - Service account: select or create one with Token Creator role
   - Audience: `https://luka-production-eb87.up.railway.app`
6. Acknowledgment deadline: **10 seconds**
7. Click **Create**

### Step 5: OAuth Consent Screen

1. Go to [APIs & Services → OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent)
2. Under **Scopes**, click **Add or Remove Scopes**
3. Add: `https://www.googleapis.com/auth/gmail.readonly`
4. Save

### Step 6: Supabase Auth Configuration

1. Go to Supabase Dashboard → Authentication → Providers → Google
2. Set **Client ID** and **Client Secret** from your GCP OAuth credentials
3. Add `gmail.readonly` to the **Additional scopes** field

### Step 7: Railway Environment Variables

Set in Railway dashboard for the backend service:

```
GCP_PROJECT_ID=<your-gcp-project-id>
PUBSUB_AUDIENCE=https://luka-production-eb87.up.railway.app
GOOGLE_CLIENT_ID=<your-oauth-client-id>
GOOGLE_CLIENT_SECRET=<your-oauth-client-secret>
TOKEN_ENCRYPTION_KEY=<generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
```

---

## 7. Dependency Changes

Add to `backend/pyproject.toml`:

```
cryptography>=43.0
```

The `google-api-python-client`, `google-auth`, and `google-auth-oauthlib` packages should already be present (used by `GmailProvider`).

---

## 8. Testing

Update existing and add new tests:

| Test file | What to test |
|-----------|-------------|
| `test_encryption.py` (new) | encrypt/decrypt round-trip, invalid key handling |
| `test_email_webhooks.py` (update) | Verify `store-provider-tokens` endpoint: stores encrypted tokens, skips null refresh token, requires auth |
| `test_email_webhooks.py` (update) | Verify `setup-email-watch` endpoint: calls setup_watch with mocked Gmail API, stores historyId and expiry |
| `test_email_parser.py` (no change) | Existing regex parsing tests still pass |
| `test_whatsapp_sender.py` (no change) | Existing sender tests still pass |

All Gmail API calls in tests should be mocked (no live API calls in CI).

---

## 9. Files Changed

| File | Change |
|------|--------|
| `core/encryption.py` | **New** — Fernet encrypt/decrypt helpers |
| `core/config.py` | Add `token_encryption_key`, `google_client_id`, `google_client_secret` |
| `modules/auth/models.py` | Add `google_access_token_enc`, `google_refresh_token_enc` columns |
| `alembic/versions/013_google_token_columns.py` | **New** — migration for token columns |
| `modules/auth/router.py` | Add `POST /auth/store-provider-tokens`, `POST /auth/setup-email-watch` |
| `frontend/app/auth/callback/route.ts` | Capture and send provider tokens to backend |
| `modules/email/gmail.py` | Pass `client_id`/`client_secret` to Credentials, expose refreshed token |
| `jobs/tasks.py` | Wire real tokens + real phone number in `process_email` and `renew_mail_watches` |
| `pyproject.toml` | Add `cryptography` dependency |

---

## 10. End-to-End Flow (After Implementation)

```
User logs in with Google → Supabase OAuth → consent screen includes gmail.readonly
                         ↓
Frontend callback captures provider_token + provider_refresh_token
                         ↓
POST /auth/store-provider-tokens → encrypted in users table
                         ↓
Onboarding completes → POST /auth/setup-email-watch
                         ↓
GmailProvider.setup_watch() → creates Pub/Sub watch on INBOX (7-day expiry)
                         ↓
Bank sends transaction email → Gmail INBOX
                         ↓
Gmail pushes notification → Pub/Sub topic → push subscription
                         ↓
POST /webhooks/gmail → OIDC verification → idempotency check → enqueue process_email
                         ↓
ARQ worker: process_email
  → decrypt user's Google tokens
  → GmailProvider.fetch_new_emails() (with auto-refresh)
  → parse_bank_email() (regex for Chilean banks)
  → lookup_merchant() (Redis → DB → LLM)
  → create Transaction (status=pending)
  → save WhatsAppSession (Redis, 30-min TTL)
  → send_expense_alert() (WhatsApp Cloud API)
                         ↓
User receives WhatsApp message → taps button → split + category saved
```
