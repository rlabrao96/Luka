# Luka — Plan 2: Transaction Pipeline

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full real-time transaction pipeline — Gmail and Outlook webhooks receive bank email alerts, parse them with regex, look up or learn merchants via Redis cache + DB + LLM, send WhatsApp interactive messages for split/category decisions, and persist the final transaction with its split and category.

**Architecture:** FastAPI webhook endpoints ACK immediately (<200ms) and enqueue ARQ jobs. The ARQ worker handles all heavy lifting: email fetching, parsing, merchant lookup, LLM calls, and WhatsApp message sending. Redis stores both the ARQ job queue and WhatsApp conversation session state. Merchant names are normalized before DB lookup to maximize cache hit rate.

**Tech Stack:** FastAPI, ARQ, Redis (asyncio), SQLAlchemy async, OpenAI gpt-4o-mini, Meta WhatsApp Cloud API, Google OIDC token verification, rapidfuzz, tenacity, google-auth

**Spec:** `docs/superpowers/specs/2026-03-10-finanzas-personales-design.md` (Sections 4 Modules 1–4)

**Prerequisite:** Plan 1 complete (all tables migrated, FastAPI running, auth working)

---

## Chunk 1: Email Provider Abstraction & Webhook Endpoints

### File Map

```
backend/
├── modules/
│   ├── email/
│   │   ├── __init__.py
│   │   ├── base.py          ← EmailProvider ABC + RawEmail dataclass
│   │   ├── factory.py       ← get_email_provider(user) → EmailProvider
│   │   ├── gmail.py         ← GmailProvider: setup_watch, fetch_new_emails, renew_watch
│   │   ├── outlook.py       ← OutlookProvider: setup_watch, fetch_new_emails, renew_watch
│   │   ├── parser.py        ← parse_bank_email(raw_text) → ParsedEmail
│   │   └── router.py        ← POST /webhooks/gmail, POST /webhooks/outlook
│   └── bank_accounts/
│       ├── __init__.py
│       ├── models.py        ← re-export BankAccount from households.models
│       ├── schemas.py       ← CreateBankAccountRequest, BankAccountResponse
│       └── router.py        ← POST /bank-accounts
└── tests/
    ├── test_email_parser.py
    └── test_email_webhooks.py
```

---

### Task 1: RawEmail Dataclass and Email Parser

**Files:**
- Create: `backend/modules/email/__init__.py`
- Create: `backend/modules/email/base.py`
- Create: `backend/modules/email/parser.py`
- Create: `backend/tests/test_email_parser.py`

- [ ] **Step 1: Write failing parser tests**

Create `backend/tests/test_email_parser.py`:
```python
import pytest
from modules.email.parser import parse_bank_email, ParsedEmail


SANTANDER_EMAIL = """
Estimado cliente,
Se ha realizado una COMPRA por $15.990 en LIDER PROVI
Fecha: 10/03/2026 14:32
Tarjeta: **** 1234
"""

BCI_EMAIL = """
Transacción realizada
Comercio: COPEC LAS CONDES
Monto: $ 32.000
Fecha: 10/03/2026 08:15
"""

CHILE_EMAIL = """
Compra aprobada en STARBUCKS PROVIDENCIA
Monto: $4.500
10/03/2026 10:05
"""


def test_parse_santander_email():
    result = parse_bank_email(SANTANDER_EMAIL)
    assert result is not None
    assert result.amount == 15990
    assert "LIDER" in result.raw_merchant
    assert result.transaction_date is not None


def test_parse_bci_email():
    result = parse_bank_email(BCI_EMAIL)
    assert result is not None
    assert result.amount == 32000
    assert "COPEC" in result.raw_merchant


def test_parse_banco_chile_email():
    result = parse_bank_email(CHILE_EMAIL)
    assert result is not None
    assert result.amount == 4500
    assert "STARBUCKS" in result.raw_merchant


def test_returns_none_for_non_transaction_email():
    result = parse_bank_email("Hola, bienvenido a tu banco.")
    assert result is None
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend
pytest tests/test_email_parser.py -v
```

Expected: `FAILED — ImportError: cannot import name 'parse_bank_email'`

- [ ] **Step 3: Create base.py with RawEmail dataclass**

Create `backend/modules/email/__init__.py` (empty).

Create `backend/modules/email/base.py`:
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RawEmail:
    message_id: str
    subject: str
    sender: str
    body: str
    received_at: datetime


@dataclass
class ParsedEmail:
    amount: int              # CLP, always integer
    raw_merchant: str        # original string from email, e.g. "COMPRA LIDER PROVI"
    transaction_date: datetime
    bank_name: str           # inferred from sender/subject


class EmailProvider(ABC):
    @abstractmethod
    async def setup_watch(self, user_id: str) -> dict: ...

    @abstractmethod
    async def fetch_new_emails(self, user_id: str, **kwargs) -> list[RawEmail]: ...

    @abstractmethod
    async def renew_watch(self, user_id: str) -> None: ...
```

- [ ] **Step 4: Create parser.py**

Create `backend/modules/email/parser.py`:
```python
import re
from datetime import datetime
from modules.email.base import ParsedEmail


# Pattern set covers Santander, BCI, Banco de Chile common alert formats
_AMOUNT_PATTERNS = [
    r'\$\s*([\d\.]+)',           # $15.990 or $ 15.990
    r'Monto:?\s*\$?\s*([\d\.]+)', # Monto: 15.990
    r'por\s+\$\s*([\d\.]+)',     # por $15.990
]

_MERCHANT_PATTERNS = [
    r'en\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9 ]{2,40})',     # en LIDER PROVI
    r'Comercio:?\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9 ]{2,40})',  # Comercio: COPEC
    r'en\s+([A-Z][A-Z0-9 ]{2,40})\n',                # en STARBUCKS\n
]

_DATE_PATTERNS = [
    r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})',  # 10/03/2026 14:32
    r'(\d{2}/\d{2}/\d{4})',                  # 10/03/2026
]


def _parse_amount(text: str) -> int | None:
    for pattern in _AMOUNT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw = match.group(1).replace(".", "").replace(",", "")
            try:
                return int(raw)
            except ValueError:
                continue
    return None


def _parse_merchant(text: str) -> str | None:
    for pattern in _MERCHANT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip().upper()
    return None


def _parse_date(text: str) -> datetime | None:
    for pattern in _DATE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            raw = match.group(1).strip()
            for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
                try:
                    return datetime.strptime(raw, fmt)
                except ValueError:
                    continue
    return None


def parse_bank_email(raw_text: str) -> ParsedEmail | None:
    """Parse a Chilean bank email alert. Returns None if not a transaction email."""
    amount = _parse_amount(raw_text)
    if amount is None:
        return None

    merchant = _parse_merchant(raw_text)
    if merchant is None:
        return None

    date = _parse_date(raw_text)
    if date is None:
        from datetime import datetime
        date = datetime.utcnow()

    return ParsedEmail(
        amount=amount,
        raw_merchant=merchant,
        transaction_date=date,
        bank_name="unknown",  # set by provider after matching email_sender_pattern
    )
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_email_parser.py -v
```

Expected: All 4 tests `PASSED`.

- [ ] **Step 6: Commit**

```bash
git add backend/modules/email/ backend/tests/test_email_parser.py
git commit -m "feat: add bank email parser with multi-pattern regex for Chilean banks"
```

---

### Task 2: Gmail and Outlook Providers

**Files:**
- Create: `backend/modules/email/gmail.py`
- Create: `backend/modules/email/outlook.py`
- Create: `backend/modules/email/factory.py`

- [ ] **Step 1: Create gmail.py**

Create `backend/modules/email/gmail.py`:
```python
import base64
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from modules.email.base import EmailProvider, RawEmail
from datetime import datetime, timezone


class GmailProvider(EmailProvider):
    def __init__(self, access_token: str, refresh_token: str):
        self._creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
        )

    def _service(self):
        return build("gmail", "v1", credentials=self._creds, cache_discovery=False)

    async def setup_watch(self, user_id: str) -> dict:
        from core.config import settings
        service = self._service()
        result = service.users().watch(
            userId="me",
            body={
                "topicName": f"projects/{settings.gcp_project_id}/topics/luka-gmail",
                "labelIds": ["INBOX"],
            },
        ).execute()
        return {"subscription_id": result.get("historyId"), "expiry": result.get("expiration")}

    async def fetch_new_emails(self, user_id: str, history_id: str = None) -> list[RawEmail]:
        service = self._service()
        if not history_id:
            return []

        history = service.users().history().list(
            userId="me", startHistoryId=history_id, historyTypes=["messageAdded"]
        ).execute()

        emails = []
        for record in history.get("history", []):
            for msg_ref in record.get("messagesAdded", []):
                msg = service.users().messages().get(
                    userId="me", id=msg_ref["message"]["id"], format="full"
                ).execute()
                emails.append(self._parse_gmail_message(msg))
        return emails

    def _parse_gmail_message(self, msg: dict) -> RawEmail:
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        body = ""
        if "data" in msg["payload"].get("body", {}):
            body = base64.urlsafe_b64decode(msg["payload"]["body"]["data"]).decode("utf-8", errors="ignore")
        return RawEmail(
            message_id=msg["id"],
            subject=headers.get("Subject", ""),
            sender=headers.get("From", ""),
            body=body,
            received_at=datetime.now(timezone.utc),
        )

    async def renew_watch(self, user_id: str) -> None:
        await self.setup_watch(user_id)
```

- [ ] **Step 2: Create outlook.py**

Create `backend/modules/email/outlook.py`:
```python
import httpx
from modules.email.base import EmailProvider, RawEmail
from datetime import datetime, timezone


GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class OutlookProvider(EmailProvider):
    def __init__(self, access_token: str):
        self._token = access_token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    async def setup_watch(self, user_id: str) -> dict:
        from core.config import settings
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{GRAPH_BASE}/subscriptions",
                headers=self._headers(),
                json={
                    "changeType": "created",
                    "notificationUrl": f"{settings.frontend_url.replace('3000', '8000')}/webhooks/outlook",
                    "resource": "me/messages",
                    "expirationDateTime": "2026-03-13T18:00:00Z",  # renewed daily
                    "clientState": settings.outlook_client_state,
                },
            )
            data = resp.json()
            return {"subscription_id": data.get("id"), "expiry": data.get("expirationDateTime")}

    async def fetch_new_emails(self, user_id: str, message_id: str = None) -> list[RawEmail]:
        if not message_id:
            return []
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GRAPH_BASE}/me/messages/{message_id}",
                headers=self._headers(),
                params={"$select": "id,subject,from,body,receivedDateTime"},
            )
            msg = resp.json()
            return [RawEmail(
                message_id=msg["id"],
                subject=msg.get("subject", ""),
                sender=msg.get("from", {}).get("emailAddress", {}).get("address", ""),
                body=msg.get("body", {}).get("content", ""),
                received_at=datetime.fromisoformat(msg.get("receivedDateTime", "").rstrip("Z")),
            )]

    async def renew_watch(self, user_id: str) -> None:
        from core.config import settings
        # Refresh subscription expiry via PATCH
        # Access token refresh handled by auth service before calling this
        async with httpx.AsyncClient() as client:
            await client.patch(
                f"{GRAPH_BASE}/subscriptions/{{subscription_id}}",
                headers=self._headers(),
                json={"expirationDateTime": "2026-03-13T18:00:00Z"},
            )
```

- [ ] **Step 3: Create factory.py**

Create `backend/modules/email/factory.py`:
```python
from modules.email.base import EmailProvider
from modules.auth.models import User


def get_email_provider(user: User, access_token: str, refresh_token: str = None) -> EmailProvider:
    if user.email_provider == "gmail":
        from modules.email.gmail import GmailProvider
        return GmailProvider(access_token=access_token, refresh_token=refresh_token or "")
    elif user.email_provider == "outlook":
        from modules.email.outlook import OutlookProvider
        return OutlookProvider(access_token=access_token)
    raise ValueError(f"Unsupported email provider: {user.email_provider}")
```

- [ ] **Step 4: Commit**

```bash
git add backend/modules/email/
git commit -m "feat: add Gmail and Outlook email providers with watch setup and fetch"
```

---

### Task 3: Webhook Endpoints

**Files:**
- Create: `backend/modules/email/router.py`
- Create: `backend/tests/test_email_webhooks.py`

- [ ] **Step 1: Write failing webhook tests**

Create `backend/tests/test_email_webhooks.py`:
```python
import pytest
import json
import base64
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_gmail_webhook_rejects_bad_token(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post("/webhooks/gmail", json={})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_gmail_webhook_accepts_valid_oidc_and_enqueues(app):
    payload = {"message": {"data": base64.b64encode(b'{}').decode(), "messageId": "msg-123"}}
    with patch("modules.email.router.verify_google_oidc_token", return_value=True), \
         patch("modules.email.router.enqueue_job", new_callable=AsyncMock) as mock_enqueue:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            response = await c.post(
                "/webhooks/gmail",
                json=payload,
                headers={"Authorization": "Bearer valid-oidc-token"},
            )
    assert response.status_code == 200
    mock_enqueue.assert_called_once()


@pytest.mark.asyncio
async def test_outlook_webhook_validation_handshake(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post("/webhooks/outlook?validationToken=abc123XYZ")
    assert response.status_code == 200
    assert response.text == "abc123XYZ"


@pytest.mark.asyncio
async def test_outlook_webhook_rejects_bad_client_state(app):
    body = {"value": [{"clientState": "wrong-secret", "resourceData": {"id": "msg-1"}}]}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post("/webhooks/outlook", json=body)
    assert response.status_code == 403
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_email_webhooks.py -v
```

Expected: `FAILED — 404 Not Found` (routes don't exist)

- [ ] **Step 3: Create email router**

Create `backend/modules/email/router.py`:
```python
import re
import base64
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from core.config import settings
from jobs.queue import enqueue_job

router = APIRouter(tags=["webhooks"])


def verify_google_oidc_token(token: str) -> bool:
    try:
        id_token.verify_oauth2_token(
            token, google_requests.Request(), audience=settings.pubsub_audience
        )
        return True
    except Exception:
        return False


@router.post("/webhooks/gmail")
async def gmail_webhook(request: Request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(403)
    token = auth_header.removeprefix("Bearer ")
    if not verify_google_oidc_token(token):
        raise HTTPException(403)

    body = await request.json()
    message = body.get("message", {})
    message_id = message.get("messageId", "")

    # Idempotency check
    from core.database import AsyncSessionLocal
    from modules.transactions.models import ProcessedWebhook
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(ProcessedWebhook).where(ProcessedWebhook.message_id == message_id))
        if existing.scalar_one_or_none():
            return {"status": "duplicate"}
        db.add(ProcessedWebhook(message_id=message_id))
        await db.commit()

    # Decode Pub/Sub data to get history_id
    data = json.loads(base64.b64decode(message.get("data", "e30=")).decode())
    history_id = data.get("historyId", "")
    email_address = data.get("emailAddress", "")

    await enqueue_job("process_email", provider="gmail", email_address=email_address, history_id=history_id)
    return {"status": "ok"}


@router.post("/webhooks/outlook")
async def outlook_webhook(request: Request, validationToken: str = None):
    if validationToken:
        if not re.match(r'^[a-zA-Z0-9\-_]{1,256}$', validationToken):
            raise HTTPException(400)
        return PlainTextResponse(validationToken)

    body = await request.json()
    for notification in body.get("value", []):
        if notification.get("clientState") != settings.outlook_client_state:
            raise HTTPException(403)

        message_id = notification.get("resourceData", {}).get("id", "")
        user_email = notification.get("clientState", "")  # enriched in production

        # Idempotency
        from core.database import AsyncSessionLocal
        from modules.transactions.models import ProcessedWebhook
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            existing = await db.execute(select(ProcessedWebhook).where(ProcessedWebhook.message_id == message_id))
            if existing.scalar_one_or_none():
                continue
            db.add(ProcessedWebhook(message_id=message_id))
            await db.commit()

        await enqueue_job("process_email", provider="outlook", message_id=message_id)

    return {"status": "ok"}
```

- [ ] **Step 4: Create jobs/queue.py (ARQ enqueue helper)**

```bash
mkdir -p backend/jobs
touch backend/jobs/__init__.py
```

Create `backend/jobs/queue.py`:
```python
import redis.asyncio as aioredis
from arq import create_pool
from arq.connections import RedisSettings
from core.config import settings


async def enqueue_job(function_name: str, **kwargs) -> None:
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await redis.enqueue_job(function_name, **kwargs)
    await redis.aclose()
```

- [ ] **Step 5: Register email router in main.py**

Edit `backend/main.py`:
```python
from modules.email.router import router as email_router
app.include_router(email_router)
```

- [ ] **Step 6: Run webhook tests**

```bash
pytest tests/test_email_webhooks.py -v
```

Expected: All 4 tests `PASSED`.

- [ ] **Step 7: Commit**

```bash
git add backend/modules/email/router.py backend/jobs/
git commit -m "feat: add Gmail and Outlook webhook endpoints with OIDC verification and idempotency"
```

---

## Chunk 2: Merchant Service (Normalization, Cache, LLM)

### File Map

```
backend/
├── modules/
│   └── merchants/
│       ├── models.py       ← (already created in Plan 1)
│       ├── normalizer.py   ← normalize_merchant(raw) → str
│       ├── service.py      ← lookup_merchant(raw) → categories
│       └── llm.py          ← categorize_with_llm(normalized) → list[str]
└── tests/
    ├── test_merchant_normalizer.py
    └── test_merchant_service.py
```

---

### Task 4: Merchant Name Normalizer

**Files:**
- Create: `backend/modules/merchants/normalizer.py`
- Create: `backend/tests/test_merchant_normalizer.py`

- [ ] **Step 1: Write failing normalizer tests**

Create `backend/tests/test_merchant_normalizer.py`:
```python
from modules.merchants.normalizer import normalize_merchant


def test_strips_compra_prefix():
    assert normalize_merchant("COMPRA LIDER PROVI") == "LIDER"


def test_strips_location_suffix():
    assert normalize_merchant("COMPRA LIDER PROVIDENCIA") == "LIDER"
    assert normalize_merchant("COMPRA LIDER LAS CONDES") == "LIDER"


def test_strips_pago_prefix():
    assert normalize_merchant("PAGO NETFLIX") == "NETFLIX"


def test_handles_no_prefix():
    assert normalize_merchant("STARBUCKS VITACURA") == "STARBUCKS"


def test_collapses_whitespace():
    assert normalize_merchant("  COPEC   ") == "COPEC"


def test_same_result_for_location_variants():
    v1 = normalize_merchant("COMPRA LIDER PROVI")
    v2 = normalize_merchant("COMPRA LIDER PROVIDENCIA")
    v3 = normalize_merchant("COMPRA LIDER LAS CONDES")
    assert v1 == v2 == v3
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_merchant_normalizer.py -v
```

Expected: `FAILED — ImportError`

- [ ] **Step 3: Implement normalizer**

Create `backend/modules/merchants/normalizer.py`:
```python
import re

_PREFIXES = re.compile(
    r'^(COMPRA|PAGO|CARGO|TRANSFERENCIA|TRF|DEBITO|CREDITO)\s+',
    re.IGNORECASE,
)

_LOCATION_SUFFIXES = re.compile(
    r'\s+(PROVI|PROVIDENCIA|LAS\s+CONDES|VITACURA|MAIPU|MAIPÚ|ÑUÑOA|'
    r'NUNOA|PUDAHUEL|QUILICURA|RECOLETA|SANTIAGO|CENTRAL|CENTRO|'
    r'NORTE|SUR|ORIENTE|PONIENTE)\s*$',
    re.IGNORECASE,
)


def normalize_merchant(raw: str) -> str:
    """
    Normalize a raw merchant name from a Chilean bank email.
    "COMPRA LIDER PROVIDENCIA" → "LIDER"
    "PAGO NETFLIX" → "NETFLIX"
    """
    s = raw.strip().upper()
    s = _PREFIXES.sub("", s)
    s = _LOCATION_SUFFIXES.sub("", s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_merchant_normalizer.py -v
```

Expected: All 6 tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/merchants/normalizer.py backend/tests/test_merchant_normalizer.py
git commit -m "feat: add merchant name normalizer for Chilean bank strings"
```

---

### Task 5: LLM Categorization

**Files:**
- Create: `backend/modules/merchants/llm.py`
- Create: `backend/tests/test_merchant_llm.py`

- [ ] **Step 1: Write failing LLM test (mocked)**

Create `backend/tests/test_merchant_llm.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_llm_returns_4_categories():
    mock_response = '{"categories": ["Supermercado", "Retail", "Alimentos", "Hogar"]}'
    with patch("modules.merchants.llm.openai_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(
            return_value=type("R", (), {
                "choices": [type("C", (), {
                    "message": type("M", (), {"content": mock_response})()
                })()]
            })()
        )
        from modules.merchants.llm import categorize_with_llm
        categories = await categorize_with_llm("LIDER")
    assert len(categories) == 4
    assert "Supermercado" in categories


@pytest.mark.asyncio
async def test_llm_returns_empty_list_on_error():
    with patch("modules.merchants.llm.openai_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API error"))
        from modules.merchants.llm import categorize_with_llm
        categories = await categorize_with_llm("UNKNOWN_MERCHANT")
    assert categories == []
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_merchant_llm.py -v
```

Expected: `FAILED — ImportError`

- [ ] **Step 3: Implement llm.py**

Create `backend/modules/merchants/llm.py`:
```python
import json
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from core.config import settings

openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

_SYSTEM_PROMPT = (
    "Eres un asistente de finanzas personales chileno. "
    "Cuando recibas el nombre de un comercio de un banco chileno, "
    "responde ÚNICAMENTE con un JSON con exactamente 4 categorías de presupuesto en español. "
    'Formato: {"categories": ["cat1","cat2","cat3","cat4"]}'
)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=5, max=30))
async def categorize_with_llm(normalized_merchant: str) -> list[str]:
    """
    Ask the LLM for 4 budget categories for the given merchant.
    Returns empty list on failure (caller falls back to manual selection).
    """
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Comercio: {normalized_merchant}"},
            ],
            temperature=0.2,
            max_tokens=100,
        )
        raw = response.choices[0].message.content
        data = json.loads(raw)
        categories = data.get("categories", [])
        return categories[:4]
    except Exception:
        return []
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_merchant_llm.py -v
```

Expected: Both tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/merchants/llm.py backend/tests/test_merchant_llm.py
git commit -m "feat: add LLM merchant categorization with retry and fallback"
```

---

### Task 6: Merchant Lookup Service (DB + Redis Cache)

**Files:**
- Create: `backend/modules/merchants/service.py`
- Create: `backend/tests/test_merchant_service.py`

- [ ] **Step 1: Write failing service tests**

Create `backend/tests/test_merchant_service.py`:
```python
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from modules.merchants.service import lookup_merchant


@pytest.mark.asyncio
async def test_returns_cached_category_on_redis_hit(db):
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=json.dumps(["Supermercado", "Retail", "Alimentos", "Hogar"]))
    result = await lookup_merchant("COMPRA LIDER PROVI", db=db, redis=mock_redis)
    assert result == ["Supermercado", "Retail", "Alimentos", "Hogar"]
    mock_redis.get.assert_called_once()


@pytest.mark.asyncio
async def test_calls_llm_on_cache_and_db_miss(db):
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    with patch("modules.merchants.service.categorize_with_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = ["Combustible", "Auto", "Transporte", "Servicios"]
        result = await lookup_merchant("COPEC VITACURA", db=db, redis=mock_redis)
    assert "Combustible" in result
    mock_llm.assert_called_once_with("COPEC")  # normalized
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_merchant_service.py -v
```

Expected: `FAILED — ImportError`

- [ ] **Step 3: Implement merchant service**

Create `backend/modules/merchants/service.py`:
```python
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from redis.asyncio import Redis
from modules.merchants.models import Merchant, MerchantCategorySelection
from modules.merchants.normalizer import normalize_merchant
from modules.merchants.llm import categorize_with_llm

_CACHE_TTL = 86400  # 24 hours


async def lookup_merchant(
    raw_name: str,
    db: AsyncSession,
    redis: Redis,
) -> list[str]:
    """
    Look up merchant categories: Redis L1 → DB L2 → LLM.
    Returns list of up to 4 category strings.
    """
    normalized = normalize_merchant(raw_name)
    cache_key = f"merchant:{normalized}"

    # L1: Redis cache
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    # L2: Database
    result = await db.execute(
        select(Merchant).where(Merchant.normalized_name == normalized)
    )
    merchant = result.scalar_one_or_none()

    if merchant:
        # Get top category by count
        top = await db.execute(
            select(MerchantCategorySelection)
            .where(MerchantCategorySelection.merchant_id == merchant.id)
            .order_by(MerchantCategorySelection.count.desc())
            .limit(4)
        )
        categories = [row.category for row in top.scalars().all()]
        if not categories and merchant.llm_suggested_categories:
            categories = merchant.llm_suggested_categories
    else:
        # L3: LLM
        categories = await categorize_with_llm(normalized)
        merchant = Merchant(
            raw_name=raw_name,
            normalized_name=normalized,
            llm_suggested_categories=categories,
        )
        db.add(merchant)
        await db.commit()
        await db.refresh(merchant)

    # Cache result in Redis
    await redis.setex(cache_key, _CACHE_TTL, json.dumps(categories))
    return categories


async def record_category_selection(
    raw_name: str,
    category: str,
    db: AsyncSession,
    redis: Redis,
) -> None:
    """Called when a user selects a final category. Trains the dataset."""
    normalized = normalize_merchant(raw_name)

    result = await db.execute(select(Merchant).where(Merchant.normalized_name == normalized))
    merchant = result.scalar_one_or_none()
    if not merchant:
        return

    # Upsert selection count
    sel_result = await db.execute(
        select(MerchantCategorySelection).where(
            MerchantCategorySelection.merchant_id == merchant.id,
            MerchantCategorySelection.category == category,
        )
    )
    selection = sel_result.scalar_one_or_none()
    if selection:
        selection.count += 1
    else:
        db.add(MerchantCategorySelection(merchant_id=merchant.id, category=category))

    merchant.total_selections += 1
    await db.commit()

    # Invalidate Redis cache so next lookup gets fresh top category
    await redis.delete(f"merchant:{normalized}")
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_merchant_service.py -v
```

Expected: Both tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/merchants/service.py backend/tests/test_merchant_service.py
git commit -m "feat: add merchant lookup service with Redis L1 cache, DB L2, and LLM fallback"
```

---

## Chunk 3: WhatsApp Integration

### File Map

```
backend/
├── modules/
│   └── whatsapp/
│       ├── __init__.py
│       ├── sender.py        ← send_expense_alert, send_category_list
│       ├── session.py       ← Redis session store for multi-step conversations
│       ├── handler.py       ← route button/list clicks to correct action
│       └── router.py        ← POST /webhooks/whatsapp
└── tests/
    ├── test_whatsapp_sender.py
    └── test_whatsapp_webhook.py
```

---

### Task 7: WhatsApp Sender

**Files:**
- Create: `backend/modules/whatsapp/__init__.py`
- Create: `backend/modules/whatsapp/sender.py`
- Create: `backend/tests/test_whatsapp_sender.py`

- [ ] **Step 1: Write failing sender tests**

Create `backend/tests/test_whatsapp_sender.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_send_personal_expense_alert_calls_meta_api():
    with patch("modules.whatsapp.sender.httpx.AsyncClient") as mock_http:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_ctx.post = AsyncMock(return_value=AsyncMock(json=lambda: {"messages": [{"id": "wamid.123"}]}))
        mock_http.return_value = mock_ctx

        from modules.whatsapp.sender import send_expense_alert
        result = await send_expense_alert(
            to="+56912345678",
            amount=15990,
            merchant="Lider",
            partner_name="Cami",
            is_joint=False,
        )
    assert result == "wamid.123"


@pytest.mark.asyncio
async def test_send_category_list_calls_meta_api():
    with patch("modules.whatsapp.sender.httpx.AsyncClient") as mock_http:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_ctx.post = AsyncMock(return_value=AsyncMock(json=lambda: {"messages": [{"id": "wamid.456"}]}))
        mock_http.return_value = mock_ctx

        from modules.whatsapp.sender import send_category_list
        result = await send_category_list(
            to="+56912345678",
            categories=["Supermercado", "Retail", "Alimentos", "Hogar"],
        )
    assert result == "wamid.456"
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_whatsapp_sender.py -v
```

Expected: `FAILED — ImportError`

- [ ] **Step 3: Implement sender.py**

Create `backend/modules/whatsapp/__init__.py` (empty).

Create `backend/modules/whatsapp/sender.py`:
```python
import httpx
from core.config import settings

_API_BASE = "https://graph.facebook.com/v19.0"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json",
    }


def _url() -> str:
    return f"{_API_BASE}/{settings.whatsapp_phone_number_id}/messages"


async def send_expense_alert(
    to: str, amount: int, merchant: str, partner_name: str, is_joint: bool
) -> str:
    """Send expense alert. Returns WhatsApp message ID."""
    if is_joint:
        body_text = f"Gasto compartido de ${amount:,} en {merchant}. ¿Qué categoría le asignamos?"
        # Joint: just ask for category, no split buttons
        return await send_category_list.__wrapped__(to=to, categories=[], context_msg=body_text)

    body_text = f"Gasto de ${amount:,} en {merchant}. ¿Cómo lo dividimos?"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body_text},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "split_personal", "title": "Mío"}},
                    {"type": "reply", "reply": {"id": "split_partner", "title": f"De {partner_name}"}},
                    {"type": "reply", "reply": {"id": "split_shared", "title": "Compartido"}},
                ]
            },
        },
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(_url(), headers=_headers(), json=payload)
        data = resp.json()
    return data["messages"][0]["id"]


async def send_category_list(to: str, categories: list[str], context_msg: str = None) -> str:
    """Send a list message with category options. Returns WhatsApp message ID."""
    rows = [{"id": f"cat_{i}", "title": cat} for i, cat in enumerate(categories)]
    body_text = context_msg or "¿A qué categoría pertenece este gasto?"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body_text},
            "action": {
                "button": "Ver categorías",
                "sections": [{"title": "Categorías", "rows": rows}],
            },
        },
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(_url(), headers=_headers(), json=payload)
        data = resp.json()
    return data["messages"][0]["id"]
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_whatsapp_sender.py -v
```

Expected: Both tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/whatsapp/sender.py backend/tests/test_whatsapp_sender.py
git commit -m "feat: add WhatsApp sender for expense alerts and category list messages"
```

---

### Task 8: WhatsApp Session State and Webhook Handler

**Files:**
- Create: `backend/modules/whatsapp/session.py`
- Create: `backend/modules/whatsapp/handler.py`
- Create: `backend/modules/whatsapp/router.py`
- Create: `backend/tests/test_whatsapp_webhook.py`

- [ ] **Step 1: Write failing webhook handler tests**

Create `backend/tests/test_whatsapp_webhook.py`:
```python
import pytest
import json
from unittest.mock import AsyncMock, patch
from modules.whatsapp.session import WhatsAppSession, save_session, get_session


@pytest.mark.asyncio
async def test_save_and_retrieve_session():
    mock_redis = AsyncMock()
    stored = {}

    async def mock_setex(key, ttl, val):
        stored[key] = val

    async def mock_get(key):
        return stored.get(key)

    mock_redis.setex = mock_setex
    mock_redis.get = mock_get

    session = WhatsAppSession(transaction_id="txn-123", step="awaiting_split")
    await save_session("+56912345678", session, mock_redis)
    retrieved = await get_session("+56912345678", mock_redis)
    assert retrieved.transaction_id == "txn-123"
    assert retrieved.step == "awaiting_split"


@pytest.mark.asyncio
async def test_get_session_returns_none_when_missing():
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    result = await get_session("+56999999999", mock_redis)
    assert result is None
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_whatsapp_webhook.py -v
```

Expected: `FAILED — ImportError`

- [ ] **Step 3: Implement session.py**

Create `backend/modules/whatsapp/session.py`:
```python
import json
from dataclasses import dataclass, asdict
from redis.asyncio import Redis

_SESSION_TTL = 1800  # 30 minutes


@dataclass
class WhatsAppSession:
    transaction_id: str
    step: str           # 'awaiting_split' | 'awaiting_category'
    split_type: str = ""
    raw_merchant: str = ""


async def save_session(phone: str, session: WhatsAppSession, redis: Redis) -> None:
    await redis.setex(f"wa_session:{phone}", _SESSION_TTL, json.dumps(asdict(session)))


async def get_session(phone: str, redis: Redis) -> WhatsAppSession | None:
    raw = await redis.get(f"wa_session:{phone}")
    if not raw:
        return None
    data = json.loads(raw)
    return WhatsAppSession(**data)


async def clear_session(phone: str, redis: Redis) -> None:
    await redis.delete(f"wa_session:{phone}")
```

- [ ] **Step 4: Implement handler.py**

Create `backend/modules/whatsapp/handler.py`:
```python
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from modules.whatsapp.session import get_session, clear_session
from modules.whatsapp.sender import send_category_list
from modules.merchants.service import record_category_selection, lookup_merchant
from modules.transactions.models import Transaction, TransactionSplit
from sqlalchemy import select
from datetime import datetime, timezone


async def handle_button_click(
    phone: str, button_id: str, db: AsyncSession, redis: Redis
) -> None:
    """Routes a WhatsApp button click to the correct action."""
    session = await get_session(phone, redis)
    if not session:
        return  # session expired, ignore

    if button_id == "split_personal":
        await _save_split(session.transaction_id, "personal", None, db)
        await clear_session(phone, redis)

    elif button_id == "split_partner":
        await _save_split(session.transaction_id, "partner", None, db)
        await clear_session(phone, redis)

    elif button_id == "split_shared":
        # Advance to category selection
        session.step = "awaiting_category"
        session.split_type = "shared"
        from modules.whatsapp.session import save_session
        await save_session(phone, session, redis)

        categories = await lookup_merchant(session.raw_merchant, db=db, redis=redis)
        await send_category_list(to=phone, categories=categories)


async def handle_list_selection(
    phone: str, list_item_id: str, list_item_title: str, db: AsyncSession, redis: Redis
) -> None:
    """Routes a WhatsApp list selection to category save."""
    session = await get_session(phone, redis)
    if not session:
        return

    category = list_item_title
    await _save_split(session.transaction_id, session.split_type or "shared", category, db)
    await record_category_selection(session.raw_merchant, category, db=db, redis=redis)
    await clear_session(phone, redis)


async def _save_split(
    transaction_id: str, split_type: str, category: str | None, db: AsyncSession
) -> None:
    result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    txn = result.scalar_one_or_none()
    if not txn:
        return

    split = TransactionSplit(
        transaction_id=txn.id,
        split_type=split_type,
        category=category,
        decided_at=datetime.now(timezone.utc),
    )
    db.add(split)
    if category:
        txn.category = category  # denormalize
    await db.commit()
```

- [ ] **Step 5: Implement WhatsApp webhook router**

Create `backend/modules/whatsapp/router.py`:
```python
import hashlib
import hmac
from fastapi import APIRouter, HTTPException, Request
from core.config import settings
from core.database import AsyncSessionLocal
from jobs.queue import enqueue_job
import redis.asyncio as aioredis

router = APIRouter(tags=["webhooks"])


def _verify_signature(body: bytes, signature: str) -> bool:
    expected = hmac.new(
        settings.whatsapp_app_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


@router.get("/webhooks/whatsapp")
async def whatsapp_verify(request: Request):
    """Meta webhook verification challenge."""
    params = request.query_params
    if params.get("hub.verify_token") == settings.whatsapp_app_secret:
        return int(params.get("hub.challenge", 0))
    raise HTTPException(403)


@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_signature(body, signature):
        raise HTTPException(403)

    import json
    data = json.loads(body)
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                phone = message["from"]
                msg_type = message.get("type")

                if msg_type == "interactive":
                    interactive = message["interactive"]
                    itype = interactive["type"]

                    redis_client = await aioredis.from_url(settings.redis_url)
                    async with AsyncSessionLocal() as db:
                        if itype == "button_reply":
                            from modules.whatsapp.handler import handle_button_click
                            await handle_button_click(
                                phone=phone,
                                button_id=interactive["button_reply"]["id"],
                                db=db,
                                redis=redis_client,
                            )
                        elif itype == "list_reply":
                            from modules.whatsapp.handler import handle_list_selection
                            await handle_list_selection(
                                phone=phone,
                                list_item_id=interactive["list_reply"]["id"],
                                list_item_title=interactive["list_reply"]["title"],
                                db=db,
                                redis=redis_client,
                            )
                    await redis_client.aclose()

    return {"status": "ok"}
```

- [ ] **Step 6: Register router in main.py**

Edit `backend/main.py`:
```python
from modules.whatsapp.router import router as whatsapp_router
app.include_router(whatsapp_router)
```

- [ ] **Step 7: Run all tests**

```bash
pytest tests/test_whatsapp_webhook.py tests/test_whatsapp_sender.py -v
```

Expected: All tests `PASSED`.

- [ ] **Step 8: Commit**

```bash
git add backend/modules/whatsapp/ backend/tests/test_whatsapp_webhook.py
git commit -m "feat: add WhatsApp webhook handler with Redis session state for multi-step conversations"
```

---

## Chunk 4: ARQ Worker — Wiring the Pipeline

### File Map

```
backend/
├── jobs/
│   ├── __init__.py
│   ├── queue.py           ← (already created)
│   └── tasks.py           ← all ARQ job functions
└── worker.py              ← updated WorkerSettings with all jobs registered
```

---

### Task 9: ARQ Jobs

**Files:**
- Create: `backend/jobs/tasks.py`
- Modify: `backend/worker.py`

- [ ] **Step 1: Create jobs/tasks.py**

Create `backend/jobs/tasks.py`:
```python
import redis.asyncio as aioredis
from core.config import settings
from core.database import AsyncSessionLocal
from modules.email.parser import parse_bank_email
from modules.merchants.service import lookup_merchant
from modules.whatsapp.sender import send_expense_alert
from modules.whatsapp.session import WhatsAppSession, save_session
from modules.transactions.models import Transaction, TransactionSplit
from modules.auth.models import User
from modules.households.models import BankAccount
from sqlalchemy import select
from datetime import datetime, timezone


async def process_email(
    ctx: dict,
    provider: str,
    email_address: str = "",
    history_id: str = "",
    message_id: str = "",
) -> None:
    """
    Core pipeline job: fetch email → parse → lookup merchant → send WhatsApp alert.
    Enqueued by Gmail/Outlook webhook endpoints.
    """
    redis_client = ctx.get("redis") or await aioredis.from_url(settings.redis_url)

    async with AsyncSessionLocal() as db:
        # Find user by email
        result = await db.execute(select(User).where(User.email == email_address))
        user = result.scalar_one_or_none()
        if not user or not user.whatsapp_verified:
            return  # can't send WhatsApp without verified number

        # Fetch email from provider
        from modules.email.factory import get_email_provider
        # Access token retrieved from Supabase Vault in production
        # For now, use a placeholder — Vault integration added in Plan 3
        provider_instance = get_email_provider(user, access_token="", refresh_token="")
        emails = await provider_instance.fetch_new_emails(
            user.id, history_id=history_id, message_id=message_id
        )

        for raw_email in emails:
            # Check bank account email_sender_pattern
            bank_result = await db.execute(
                select(BankAccount).where(
                    BankAccount.user_id == user.id,
                    BankAccount.is_active == True,
                )
            )
            bank_account = bank_result.scalars().first()

            # Parse email
            parsed = parse_bank_email(raw_email.body)
            if not parsed:
                continue

            # Lookup merchant categories
            categories = await lookup_merchant(
                parsed.raw_merchant, db=db, redis=redis_client
            )

            # Create pending transaction
            txn = Transaction(
                user_id=user.id,
                household_id=None,  # enriched from bank_account below
                bank_account_id=bank_account.id if bank_account else None,
                raw_merchant_name=parsed.raw_merchant,
                amount=parsed.amount,
                transaction_date=parsed.transaction_date,
                source=provider,
                status="pending",
                raw_email_text=raw_email.body,
            )

            # Set household from bank account
            if bank_account:
                txn.household_id = bank_account.household_id

                if bank_account.account_type == "joint":
                    # Auto-classify as shared, just ask for category
                    split = TransactionSplit(
                        transaction_id=txn.id,
                        split_type="shared",
                    )
                    db.add(split)

            db.add(txn)
            await db.commit()
            await db.refresh(txn)

            # Build WhatsApp session
            # Retrieve phone from Supabase Vault (placeholder)
            phone = "+56900000000"  # TODO: retrieve from Vault in Plan 3

            is_joint = bank_account and bank_account.account_type == "joint"
            session = WhatsAppSession(
                transaction_id=str(txn.id),
                step="awaiting_category" if is_joint else "awaiting_split",
                raw_merchant=parsed.raw_merchant,
            )
            await save_session(phone, session, redis_client)

            # Send WhatsApp message
            await send_expense_alert(
                to=phone,
                amount=parsed.amount,
                merchant=parsed.raw_merchant,
                partner_name="tu pareja",
                is_joint=is_joint,
            )


async def renew_mail_watches(ctx: dict) -> None:
    """Daily job: renew Gmail (7d) and Outlook (~3d) subscriptions."""
    from datetime import timedelta
    async with AsyncSessionLocal() as db:
        from sqlalchemy import and_
        cutoff = datetime.now(timezone.utc) + timedelta(hours=24)
        result = await db.execute(
            select(User).where(
                and_(User.mail_watch_expiry != None, User.mail_watch_expiry <= cutoff)
            )
        )
        users = result.scalars().all()
        for user in users:
            try:
                from modules.email.factory import get_email_provider
                provider = get_email_provider(user, access_token="")
                await provider.renew_watch(str(user.id))
            except Exception as e:
                await _record_failed_job("renew_mail_watches", {"user_id": str(user.id)}, str(e), db)


async def purge_raw_emails(ctx: dict) -> None:
    """Hourly job: clear raw_email_text after 24h."""
    from datetime import timedelta
    async with AsyncSessionLocal() as db:
        from sqlalchemy import update, and_
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        await db.execute(
            update(Transaction)
            .where(and_(Transaction.raw_email_text != None, Transaction.created_at < cutoff))
            .values(raw_email_text=None)
        )
        await db.commit()


async def cleanup_processed_webhooks(ctx: dict) -> None:
    """Daily job: delete idempotency records older than 7 days."""
    from datetime import timedelta
    from modules.transactions.models import ProcessedWebhook
    from sqlalchemy import delete
    async with AsyncSessionLocal() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        await db.execute(delete(ProcessedWebhook).where(ProcessedWebhook.processed_at < cutoff))
        await db.commit()


async def _record_failed_job(job_name: str, payload: dict, error: str, db) -> None:
    from modules.transactions.models import FailedJob
    db.add(FailedJob(job_name=job_name, payload=payload, error_message=error))
    await db.commit()
```

- [ ] **Step 2: Update worker.py with all jobs registered**

Replace `backend/worker.py`:
```python
import redis.asyncio as aioredis
from arq import cron
from core.config import settings
from jobs.tasks import (
    process_email,
    renew_mail_watches,
    purge_raw_emails,
    cleanup_processed_webhooks,
)


async def startup(ctx: dict) -> None:
    ctx["redis"] = await aioredis.from_url(settings.redis_url)


async def shutdown(ctx: dict) -> None:
    await ctx["redis"].aclose()


class WorkerSettings:
    functions = [process_email]
    cron_jobs = [
        cron(renew_mail_watches, hour=3, minute=0),          # 3am daily
        cron(purge_raw_emails, minute=0),                     # every hour
        cron(cleanup_processed_webhooks, hour=4, minute=0),   # 4am daily
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = settings.redis_url
    max_jobs = 10
    job_timeout = 60
```

- [ ] **Step 3: Run full test suite**

```bash
pytest tests/ -v --tb=short
```

Expected: All tests pass. Note any failures and fix before continuing.

- [ ] **Step 4: Commit**

```bash
git add backend/jobs/tasks.py backend/worker.py
git commit -m "feat: wire ARQ worker with process_email pipeline and maintenance cron jobs"
```

---

## Plan 2 Complete ✅

**What you now have:**
- Gmail OIDC-verified and Outlook webhook endpoints with idempotency
- Bank email parser covering Santander, BCI, Banco de Chile formats
- Merchant normalizer (strips Chilean bank prefixes/location suffixes)
- Merchant lookup: Redis L1 → DB L2 → LLM (gpt-4o-mini) with retry
- WhatsApp sender: expense alerts (personal + joint) and category lists
- WhatsApp session store in Redis for multi-step conversations
- WhatsApp webhook handler routing button and list clicks
- Full ARQ pipeline job: email → parse → merchant → WhatsApp → save transaction
- Maintenance cron jobs: watch renewal, email purge, webhook cleanup

**Next:** [Plan 3 — Household Logic](./2026-03-10-luka-plan-3-household-logic.md)
(RLS policies, partner stats, Fintoc reconciliation, joint budget tracking)
