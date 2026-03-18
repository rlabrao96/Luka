# Fintoc Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the manual bank account form with Fintoc Link widget, auto-import 90 days of transaction history on connect, and track import progress with a dashboard banner.

**Architecture:** Fintoc JS widget runs in-browser and returns a `link_token`. Backend fetches the account list from Fintoc API using that token (spec deviation: original spec assumed frontend gets account list from widget; a backend proxy endpoint is added instead to keep Fintoc API key server-side only). On confirm, backend creates `BankAccount` records and enqueues one `import_fintoc_history` ARQ job per account, which fetches 90 days of transactions and inserts them as settled+uncategorized with auto-assigned splits.

**Tech Stack:** FastAPI + SQLAlchemy async + ARQ + httpx (backend) | Next.js App Router + Tailwind + shadcn/ui (frontend) | Fintoc JS SDK

**Spec:** `docs/superpowers/specs/2026-03-18-fintoc-integration-design.md`

---

## Frontend Baseline

Before any implementation begins, the frontend must be verified clean:

```bash
cd frontend && npx tsc --noEmit && npm run build
```

**Confirmed baseline (2026-03-18):** TypeScript passes, all 14 routes build successfully. Any frontend phase that introduces TypeScript errors or build failures must fix them before merging.

---

## Execution Map

```
PHASE 1 (sequential): Tasks 1–4   ← migrations + model + module scaffold
    ↓
PHASE 2 (3 parallel agents):
    Agent A: Tasks 5–9   ← backend routes + FintocClient.fetch_accounts
    Agent B: Tasks 10–12 ← backend import job
    Agent C: Tasks 13–14 ← frontend api.ts + FintocAccountPicker
             Task C-V    ← frontend verification agent (TypeScript + build)
    ↓ (all three must complete, including C-V approval)
PHASE 3 (2 parallel agents):
    Agent D: Task 15     ← connect-bank page rewrite
             Task D-V    ← frontend verification agent
    Agent E: Tasks 16–19 ← status banner + settings
             Task E-V    ← frontend verification agent
    ↓
PHASE 4 (sequential): Task 20    ← worker.py + migrations + full smoke test
```

**Verification agents (C-V, D-V, E-V):** After each frontend agent completes, a separate verification agent runs `tsc --noEmit` + `npm run build`, reads the full error output, fixes any issues it finds, and commits the fix before the phase is considered done. The implementing agent does NOT self-verify — verification is always a separate agent with fresh eyes.

---

## PHASE 1 — Foundation
> **One agent. Run sequentially. All later phases depend on this.**

### Task 1: Migration 004 — Enforce valid account_type values

**Files:**
- Create: `backend/alembic/versions/004_account_type_constraint.py`

- [ ] **Step 1: Write the migration**

The constraint is safe: existing data only contains `'personal'` or `'joint'` (both allowed by the new constraint). The constraint also allows `'partner'` going forward.

```python
"""Enforce account_type IN ('personal', 'partner', 'joint').

Revision ID: 004
Down revision: 003
"""
from alembic import op

revision = "004"
down_revision = "003"


def upgrade():
    # Existing rows only have 'personal' or 'joint' — both valid under new constraint.
    op.execute(
        "ALTER TABLE bank_accounts "
        "ADD CONSTRAINT chk_bank_account_type "
        "CHECK (account_type IN ('personal', 'partner', 'joint'))"
    )


def downgrade():
    op.execute(
        "ALTER TABLE bank_accounts "
        "DROP CONSTRAINT IF EXISTS chk_bank_account_type"
    )
```

- [ ] **Step 2: Commit**

```bash
git add backend/alembic/versions/004_account_type_constraint.py
git commit -m "feat: migration 004 - enforce account_type values (personal|partner|joint)"
```

---

### Task 2: Migration 005 — Add import_status to bank_accounts

**Files:**
- Create: `backend/alembic/versions/005_bank_account_import_status.py`

- [ ] **Step 1: Write the migration**

```python
"""Add import_status column to bank_accounts.

Revision ID: 005
Down revision: 004
"""
import sqlalchemy as sa
from alembic import op

revision = "005"
down_revision = "004"


def upgrade():
    op.add_column(
        "bank_accounts",
        sa.Column(
            "import_status",
            sa.String(),
            nullable=False,
            server_default="done",
        ),
    )


def downgrade():
    op.drop_column("bank_accounts", "import_status")
```

- [ ] **Step 2: Commit**

```bash
git add backend/alembic/versions/005_bank_account_import_status.py
git commit -m "feat: migration 005 - add bank_accounts.import_status"
```

---

### Task 3: Update BankAccount SQLAlchemy model

**Files:**
- Modify: `backend/modules/households/models.py`

- [ ] **Step 1: Update account_type comment and add import_status field**

In `backend/modules/households/models.py`, inside the `BankAccount` class:

Change line 48 (account_type comment):
```python
    # OLD:
    account_type: Mapped[str] = mapped_column(String, nullable=False)  # 'personal' | 'joint'
    # NEW:
    account_type: Mapped[str] = mapped_column(String, nullable=False)  # 'personal' | 'partner' | 'joint'
```

Add `import_status` after `is_active` (after line 53):
```python
    import_status: Mapped[str] = mapped_column(String, default="done")  # 'pending'|'importing'|'done'|'failed'
```

The final `BankAccount` class should look like:
```python
class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    bank_name: Mapped[str] = mapped_column(String, nullable=False)
    account_type: Mapped[str] = mapped_column(String, nullable=False)  # 'personal' | 'partner' | 'joint'
    cardholder_name: Mapped[str | None] = mapped_column(String, nullable=True)
    email_sender_pattern: Mapped[str | None] = mapped_column(String, nullable=True)
    fintoc_link_id: Mapped[str | None] = mapped_column(String, nullable=True)
    fintoc_account_id: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    import_status: Mapped[str] = mapped_column(String, default="done")  # 'pending'|'importing'|'done'|'failed'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: Verify the model compiles**

```bash
cd backend && python -c "from modules.households.models import BankAccount; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/modules/households/models.py
git commit -m "feat: add import_status to BankAccount model, allow partner account_type"
```

---

### Task 4: Create bank_accounts module and register in main.py

**Files:**
- Create: `backend/modules/bank_accounts/__init__.py`
- Create: `backend/modules/bank_accounts/router.py` (skeleton only)
- Modify: `backend/main.py`

- [ ] **Step 1: Create the module init**

`backend/modules/bank_accounts/__init__.py`:
```python
```
(empty file)

- [ ] **Step 2: Create the router skeleton**

`backend/modules/bank_accounts/router.py`:
```python
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.households.models import BankAccount, HouseholdMember

router = APIRouter(prefix="/bank-accounts", tags=["bank-accounts"])


async def _require_household_membership(
    household_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> None:
    """Raise 403 if user is not a member of the household."""
    result = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.user_id == user_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this household")
```

- [ ] **Step 3: Register the router in main.py**

In `backend/main.py`, add the import after the existing router imports:
```python
from modules.bank_accounts.router import router as bank_accounts_router
```

And inside `create_app()`, after `app.include_router(budgets_router)`:
```python
    app.include_router(bank_accounts_router)
```

- [ ] **Step 4: Verify FastAPI starts**

```bash
cd backend && python -c "from main import app; print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/modules/bank_accounts/ backend/main.py
git commit -m "feat: add bank_accounts module scaffold and register router at /bank-accounts"
```

---

## PHASE 2 — Parallel Implementation
> **🚦 Start all three agents simultaneously after Phase 1 is merged to main.**

---

## PHASE 2 — Agent A: Backend Routes
> **Tasks 5–9. Independent from Agent B and C.**

### Task 5: Add fetch_accounts to FintocClient

**Files:**
- Modify: `backend/modules/fintoc/client.py`

The existing `FintocClient` already has `_headers()` and `fetch_transactions()`. We add `fetch_accounts()` which calls `GET /v1/accounts` using the same link token header — no new credentials needed.

- [ ] **Step 1: Write a failing test**

Create `backend/tests/test_fintoc_client_accounts.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from modules.fintoc.client import FintocClient


@pytest.mark.asyncio
async def test_fetch_accounts_returns_account_list():
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"id": "acc_123", "name": "Cuenta Corriente", "type": "checking_account", "number": "****1234"},
        {"id": "acc_456", "name": "Tarjeta de Crédito", "type": "credit_card", "number": "****5678"},
    ]
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as MockHttpx:
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.get = AsyncMock(return_value=mock_response)
        MockHttpx.return_value = mock_http

        client = FintocClient(link_token="lt_test")
        accounts = await client.fetch_accounts()

    assert len(accounts) == 2
    assert accounts[0]["id"] == "acc_123"
    assert accounts[1]["type"] == "credit_card"
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd backend && python -m pytest tests/test_fintoc_client_accounts.py -v
```
Expected: `AttributeError: 'FintocClient' object has no attribute 'fetch_accounts'`

- [ ] **Step 3: Implement fetch_accounts**

Add this method to the `FintocClient` class in `backend/modules/fintoc/client.py`:
```python
    async def fetch_accounts(self) -> list[dict]:
        """Fetch all accounts associated with this link token."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.fintoc.com/v1/accounts",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()
```

- [ ] **Step 4: Run — expect PASS**

```bash
cd backend && python -m pytest tests/test_fintoc_client_accounts.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/modules/fintoc/client.py backend/tests/test_fintoc_client_accounts.py
git commit -m "feat: add FintocClient.fetch_accounts()"
```

---

### Task 6: Add route test fixtures to conftest.py

**Files:**
- Modify: `backend/tests/conftest.py`

The existing conftest has `db`, `mock_user`, `mock_partner`, `mock_household`. Route tests need an HTTP client and auth override fixtures.

- [ ] **Step 1: Add client and auth fixtures**

Append to `backend/tests/conftest.py`:
```python
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from modules.households.models import BankAccount


@pytest.fixture
async def http_client(app):
    """AsyncClient wired to the FastAPI app with ASGI transport."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def mock_current_user(mock_user):
    """Returns the mock_user. Used to override get_current_user dependency."""
    return mock_user


@pytest.fixture
def override_auth(app, mock_current_user):
    """Override get_current_user so routes think a user is authenticated."""
    from core.security import get_current_user
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_db_session():
    """Async mock of an SQLAlchemy AsyncSession."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def override_db(app, mock_db_session):
    """Override get_db so routes use the mock session."""
    from core.database import get_db

    async def _mock_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = _mock_db
    yield mock_db_session
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Verify conftest loads**

```bash
cd backend && python -m pytest tests/ --collect-only -q 2>&1 | head -5
```
Expected: No import errors.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test: add http_client, override_auth, override_db fixtures to conftest"
```

---

### Task 7: GET /bank-accounts/fintoc/accounts endpoint

**Files:**
- Modify: `backend/modules/bank_accounts/router.py`
- Create: `backend/tests/test_bank_accounts_routes.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_bank_accounts_routes.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.orm import MagicMock


@pytest.mark.asyncio
async def test_get_fintoc_accounts_returns_list(http_client, override_auth, override_db):
    mock_accounts = [
        {"id": "acc_1", "name": "Cuenta Corriente", "type": "checking_account", "number": "****1234"},
    ]
    with patch("modules.bank_accounts.router.FintocClient") as MockClient:
        instance = AsyncMock()
        instance.fetch_accounts = AsyncMock(return_value=mock_accounts)
        MockClient.return_value = instance

        response = await http_client.get("/bank-accounts/fintoc/accounts?link_token=lt_test")

    assert response.status_code == 200
    assert response.json() == mock_accounts


@pytest.mark.asyncio
async def test_get_fintoc_accounts_requires_auth(http_client):
    response = await http_client.get("/bank-accounts/fintoc/accounts?link_token=lt_test")
    assert response.status_code in (401, 403)  # unauthenticated
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd backend && python -m pytest tests/test_bank_accounts_routes.py::test_get_fintoc_accounts_returns_list -v
```
Expected: `404 Not Found` (route doesn't exist yet)

- [ ] **Step 3: Implement the endpoint**

Add to `backend/modules/bank_accounts/router.py`:
```python
import httpx
from modules.fintoc.client import FintocClient


@router.get("/fintoc/accounts")
async def get_fintoc_accounts(
    link_token: str,
    current_user: User = Depends(get_current_user),
):
    """Fetch available accounts for a Fintoc link token. Called after widget success."""
    client = FintocClient(link_token=link_token)
    try:
        accounts = await client.fetch_accounts()
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=400, detail="Failed to fetch accounts from Fintoc")
    return accounts
```

- [ ] **Step 4: Run — expect PASS**

```bash
cd backend && python -m pytest tests/test_bank_accounts_routes.py::test_get_fintoc_accounts_returns_list -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/modules/bank_accounts/router.py backend/tests/test_bank_accounts_routes.py
git commit -m "feat: GET /bank-accounts/fintoc/accounts - proxy Fintoc account list"
```

---

### Task 8: POST /bank-accounts/fintoc/connect endpoint

**Files:**
- Modify: `backend/modules/bank_accounts/router.py`
- Modify: `backend/tests/test_bank_accounts_routes.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_bank_accounts_routes.py`:
```python
import uuid
from unittest.mock import patch, MagicMock


HOUSEHOLD_ID = str(uuid.uuid4())


@pytest.mark.asyncio
async def test_connect_fintoc_returns_403_if_not_member(http_client, override_auth, override_db):
    # mock_db_session.scalar returns None (not a member)
    override_db.scalar = AsyncMock(return_value=None)

    response = await http_client.post(
        "/bank-accounts/fintoc/connect",
        json={
            "link_token": "lt_test",
            "household_id": HOUSEHOLD_ID,
            "accounts": [{"fintoc_account_id": "acc_1", "label": "personal"}],
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_connect_fintoc_creates_accounts(http_client, override_auth, override_db, mock_current_user):
    mock_member = MagicMock()
    # First scalar call: membership check (member found)
    # Second scalar call: duplicate check (None = no duplicate)
    override_db.scalar = AsyncMock(side_effect=[mock_member, None, None])
    override_db.flush = AsyncMock()

    with patch("modules.bank_accounts.router.enqueue_job", AsyncMock(return_value=None)):
        response = await http_client.post(
            "/bank-accounts/fintoc/connect",
            json={
                "link_token": "lt_abc",
                "household_id": HOUSEHOLD_ID,
                "accounts": [
                    {"fintoc_account_id": "acc_1", "label": "personal"},
                    {"fintoc_account_id": "acc_2", "label": "joint"},
                ],
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["created"] == 2


@pytest.mark.asyncio
async def test_connect_fintoc_returns_409_on_duplicate(http_client, override_auth, override_db):
    mock_member = MagicMock()
    mock_existing = MagicMock()  # existing account found
    override_db.scalar = AsyncMock(side_effect=[mock_member, mock_existing])

    response = await http_client.post(
        "/bank-accounts/fintoc/connect",
        json={
            "link_token": "lt_abc",
            "household_id": HOUSEHOLD_ID,
            "accounts": [{"fintoc_account_id": "acc_duplicate", "label": "personal"}],
        },
    )
    assert response.status_code == 409
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd backend && python -m pytest tests/test_bank_accounts_routes.py -k "connect" -v
```

- [ ] **Step 3: Implement the endpoint**

Add to `backend/modules/bank_accounts/router.py`:
```python
from jobs.queue import enqueue_job


class FintocAccountIn(BaseModel):
    fintoc_account_id: str
    label: str  # "personal" | "partner" | "joint"


class ConnectFintocRequest(BaseModel):
    link_token: str
    household_id: uuid.UUID
    accounts: list[FintocAccountIn]


@router.post("/fintoc/connect")
async def connect_fintoc_accounts(
    body: ConnectFintocRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Store Fintoc-connected accounts and enqueue 90-day history import per account."""
    await _require_household_membership(body.household_id, current_user.id, db)

    # Check for duplicates before creating anything
    for acct in body.accounts:
        existing = await db.scalar(
            select(BankAccount).where(BankAccount.fintoc_account_id == acct.fintoc_account_id)
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Account {acct.fintoc_account_id} is already connected",
            )

    # Create and enqueue
    created = []
    for acct in body.accounts:
        bank_account = BankAccount(
            household_id=body.household_id,
            user_id=current_user.id,
            bank_name="fintoc",
            account_type=acct.label,
            fintoc_link_id=body.link_token,
            fintoc_account_id=acct.fintoc_account_id,
            import_status="pending",
        )
        db.add(bank_account)
        await db.flush()
        created.append(bank_account)
        await enqueue_job("import_fintoc_history", bank_account_id=str(bank_account.id))

    await db.commit()
    return {
        "created": len(created),
        "accounts": [
            {"id": str(a.id), "fintoc_account_id": a.fintoc_account_id, "account_type": a.account_type}
            for a in created
        ],
    }
```

- [ ] **Step 4: Run — expect PASS**

```bash
cd backend && python -m pytest tests/test_bank_accounts_routes.py -k "connect" -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/modules/bank_accounts/router.py backend/tests/test_bank_accounts_routes.py
git commit -m "feat: POST /bank-accounts/fintoc/connect - create accounts and enqueue import"
```

---

### Task 9: GET /bank-accounts/import-status endpoint

**Files:**
- Modify: `backend/modules/bank_accounts/router.py`
- Modify: `backend/tests/test_bank_accounts_routes.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_bank_accounts_routes.py`:
```python
@pytest.mark.asyncio
async def test_import_status_403_if_not_member(http_client, override_auth, override_db):
    override_db.scalar = AsyncMock(return_value=None)  # not a member
    response = await http_client.get(
        f"/bank-accounts/import-status?household_id={HOUSEHOLD_ID}"
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_import_status_true_when_pending_accounts_exist(http_client, override_auth, override_db):
    mock_member = MagicMock()
    mock_pending_account = MagicMock()
    override_db.scalar = AsyncMock(return_value=mock_member)  # membership check passes
    # execute().scalars().first() returns a pending account
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_pending_account
    override_db.execute = AsyncMock(return_value=mock_result)

    response = await http_client.get(
        f"/bank-accounts/import-status?household_id={HOUSEHOLD_ID}"
    )
    assert response.status_code == 200
    assert response.json() == {"importing": True}


@pytest.mark.asyncio
async def test_import_status_false_when_all_done(http_client, override_auth, override_db):
    mock_member = MagicMock()
    override_db.scalar = AsyncMock(return_value=mock_member)
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None  # no pending accounts
    override_db.execute = AsyncMock(return_value=mock_result)

    response = await http_client.get(
        f"/bank-accounts/import-status?household_id={HOUSEHOLD_ID}"
    )
    assert response.status_code == 200
    assert response.json() == {"importing": False}
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd backend && python -m pytest tests/test_bank_accounts_routes.py -k "import_status" -v
```

- [ ] **Step 3: Implement the endpoint**

Add to `backend/modules/bank_accounts/router.py`:
```python
@router.get("/import-status")
async def get_import_status(
    household_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Poll whether any account in this household is still importing history."""
    await _require_household_membership(household_id, current_user.id, db)

    result = await db.execute(
        select(BankAccount).where(
            BankAccount.household_id == household_id,
            BankAccount.import_status.in_(["pending", "importing"]),
        )
    )
    importing = result.scalars().first() is not None
    return {"importing": importing}
```

- [ ] **Step 4: Run all route tests — expect PASS**

```bash
cd backend && python -m pytest tests/test_bank_accounts_routes.py tests/test_fintoc_client_accounts.py -v
```
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/bank_accounts/router.py backend/tests/test_bank_accounts_routes.py
git commit -m "feat: GET /bank-accounts/import-status - poll household import progress"
```

---

## PHASE 2 — Agent B: Backend Import Job
> **Tasks 10–12. Independent from Agent A and C.**

### Task 10: Add enqueue helper to queue.py

**Files:**
- Modify: `backend/jobs/queue.py`

- [ ] **Step 1: Add the typed helper**

In `backend/jobs/queue.py`, append after the existing `enqueue_job` function:
```python
async def enqueue_fintoc_history_import(bank_account_id: str) -> None:
    """Enqueue a 90-day Fintoc history import for a single bank account."""
    await enqueue_job("import_fintoc_history", bank_account_id=bank_account_id)
```

- [ ] **Step 2: Verify**

```bash
cd backend && python -c "from jobs.queue import enqueue_fintoc_history_import; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/jobs/queue.py
git commit -m "feat: add enqueue_fintoc_history_import helper to queue.py"
```

---

### Task 11: import_fintoc_history ARQ job

**Files:**
- Modify: `backend/jobs/tasks.py`
- Create: `backend/tests/test_fintoc_import.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_fintoc_import.py`:
```python
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call
from modules.fintoc.client import FintocTransaction
from modules.transactions.models import TransactionSplit


def make_fintoc_txn(id: str, amount: int = 10000, description: str = "LIDER") -> FintocTransaction:
    return FintocTransaction(
        id=id,
        amount=amount,
        description=description,
        transaction_date=datetime(2026, 1, 15, tzinfo=timezone.utc),
        account_id="acc_test",
    )


def make_mock_account(account_type: str = "personal"):
    account = MagicMock()
    account.id = "ba_1"
    account.fintoc_link_id = "lt_test"
    account.fintoc_account_id = "acc_test"
    account.account_type = account_type
    account.user_id = "user_1"
    account.household_id = "hh_1"
    return account


@pytest.mark.asyncio
async def test_import_creates_transactions_and_splits():
    """Happy path: two Fintoc transactions → two Transaction + two TransactionSplit rows."""
    from jobs.tasks import import_fintoc_history

    mock_account = make_mock_account("personal")
    added_objects = []

    with patch("jobs.tasks.AsyncSessionLocal") as MockSession, \
         patch("jobs.tasks.FintocClient") as MockClient:

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_account)
        mock_db.scalar = AsyncMock(return_value=None)  # no existing fintoc_id
        mock_db.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        MockSession.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        MockSession.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_client = AsyncMock()
        mock_client.fetch_transactions = AsyncMock(return_value=[
            make_fintoc_txn("ft_1"),
            make_fintoc_txn("ft_2", description="UBER"),
        ])
        MockClient.return_value = mock_client

        await import_fintoc_history({}, bank_account_id="ba_1")

    from modules.transactions.models import Transaction
    transactions = [o for o in added_objects if isinstance(o, Transaction)]
    splits = [o for o in added_objects if isinstance(o, TransactionSplit)]
    assert len(transactions) == 2
    assert len(splits) == 2
    assert mock_account.import_status == "done"


@pytest.mark.asyncio
async def test_import_skips_existing_fintoc_id():
    """Idempotency: if fintoc_id already in DB, skip without creating duplicate."""
    from jobs.tasks import import_fintoc_history

    mock_account = make_mock_account()

    with patch("jobs.tasks.AsyncSessionLocal") as MockSession, \
         patch("jobs.tasks.FintocClient") as MockClient:

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_account)
        mock_db.scalar = AsyncMock(return_value=MagicMock())  # existing txn found
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        MockSession.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        MockSession.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_client = AsyncMock()
        mock_client.fetch_transactions = AsyncMock(return_value=[make_fintoc_txn("ft_exists")])
        MockClient.return_value = mock_client

        await import_fintoc_history({}, bank_account_id="ba_1")

    mock_db.add.assert_not_called()
    assert mock_account.import_status == "done"


@pytest.mark.asyncio
@pytest.mark.parametrize("account_type,expected_split", [
    ("personal", "personal"),
    ("partner", "partner"),
    ("joint", "shared"),
])
async def test_import_split_type_mapping(account_type, expected_split):
    """Account label correctly maps to TransactionSplit.split_type."""
    from jobs.tasks import import_fintoc_history

    mock_account = make_mock_account(account_type)
    added_objects = []

    with patch("jobs.tasks.AsyncSessionLocal") as MockSession, \
         patch("jobs.tasks.FintocClient") as MockClient:

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_account)
        mock_db.scalar = AsyncMock(return_value=None)
        mock_db.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        MockSession.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        MockSession.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_client = AsyncMock()
        mock_client.fetch_transactions = AsyncMock(return_value=[make_fintoc_txn("ft_1")])
        MockClient.return_value = mock_client

        await import_fintoc_history({}, bank_account_id="ba_1")

    splits = [o for o in added_objects if isinstance(o, TransactionSplit)]
    assert len(splits) == 1
    assert splits[0].split_type == expected_split


@pytest.mark.asyncio
async def test_import_sets_status_failed_on_error():
    """On Fintoc API error, import_status is set to 'failed' and job is logged."""
    from jobs.tasks import import_fintoc_history

    mock_account = make_mock_account()

    with patch("jobs.tasks.AsyncSessionLocal") as MockSession, \
         patch("jobs.tasks.FintocClient") as MockClient:

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_account)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        MockSession.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        MockSession.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_client = AsyncMock()
        mock_client.fetch_transactions = AsyncMock(side_effect=Exception("Fintoc API down"))
        MockClient.return_value = mock_client

        await import_fintoc_history({}, bank_account_id="ba_1")

    assert mock_account.import_status == "failed"
    # A FailedJob should have been added
    from modules.transactions.models import FailedJob
    failed_jobs = [o for o in mock_db.add.call_args_list if isinstance(o.args[0], FailedJob)]
    assert len(failed_jobs) == 1
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd backend && python -m pytest tests/test_fintoc_import.py -v
```
Expected: `ImportError` (function doesn't exist yet)

- [ ] **Step 3: Implement the job in tasks.py**

First, add `FintocClient` to the imports at the top of `backend/jobs/tasks.py`:
```python
from modules.fintoc.client import FintocClient
```
(The other required imports — `AsyncSessionLocal`, `Transaction`, `TransactionSplit`, `FailedJob`, `BankAccount`, `select`, `datetime`, `timedelta`, `timezone` — are already present in `tasks.py`.)

Then add this function to `backend/jobs/tasks.py` (after `run_fintoc_sync`):
```python
async def import_fintoc_history(ctx: dict, bank_account_id: str) -> None:
    """
    One-shot job: import 90 days of Fintoc transactions for a bank account.
    Triggered when a user connects a bank account via Fintoc Link.
    Idempotent: skips any transaction whose fintoc_id already exists in the DB.
    """
    from datetime import date

    split_map = {
        "personal": "personal",
        "partner": "partner",
        "joint": "shared",
    }

    async with AsyncSessionLocal() as db:
        account = await db.get(BankAccount, bank_account_id)
        if not account or not account.fintoc_link_id or not account.fintoc_account_id:
            return

        account.import_status = "importing"
        await db.commit()

        try:
            client = FintocClient(link_token=account.fintoc_link_id)
            fintoc_txns = await client.fetch_transactions(
                account_id=account.fintoc_account_id,
                since=date.today() - timedelta(days=90),
                until=date.today(),
            )

            for ftxn in fintoc_txns:
                existing = await db.scalar(
                    select(Transaction).where(Transaction.fintoc_id == ftxn.id)
                )
                if existing:
                    continue

                txn = Transaction(
                    user_id=account.user_id,
                    household_id=account.household_id,
                    bank_account_id=account.id,
                    raw_merchant_name=ftxn.description,
                    amount=ftxn.amount,
                    currency="CLP",
                    transaction_date=ftxn.transaction_date,
                    source="fintoc",
                    status="settled",
                    fintoc_id=ftxn.id,
                )
                db.add(txn)
                await db.flush()

                split = TransactionSplit(
                    transaction_id=txn.id,
                    split_type=split_map.get(account.account_type, "personal"),
                    decided_by_user_id=account.user_id,
                    decided_at=datetime.now(timezone.utc),
                )
                db.add(split)

            # Set status to done and commit everything in one shot
            account.import_status = "done"
            await db.commit()

        except Exception as e:
            account.import_status = "failed"
            await db.commit()
            await _record_failed_job(
                "import_fintoc_history",
                {"bank_account_id": bank_account_id},
                str(e),
                db,
            )
```

**Note on single commit:** `import_status = "done"` is set inside the `try` block before the final `await db.commit()`, so all inserts and the status update commit atomically. This avoids the expired-object issue that would occur if we called `commit()` and then tried to modify the account object afterward.

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd backend && python -m pytest tests/test_fintoc_import.py -v
```
Expected: All 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/jobs/tasks.py backend/tests/test_fintoc_import.py
git commit -m "feat: import_fintoc_history ARQ job - 90-day history import with idempotency"
```

---

### Task 12: Run full backend test suite

- [ ] **Step 1: Run all tests**

```bash
cd backend && python -m pytest tests/ -v
```
Expected: All existing tests still pass + new tests pass. No regressions.

- [ ] **Step 2: Commit if any fixes were needed**

```bash
git add -A && git commit -m "fix: resolve any test conflicts after import job"
```

---

## PHASE 2 — Agent C: Frontend Foundation
> **Tasks 13–14. Independent from Agent A and B.**

### Task 13: Add Fintoc types and API methods to api.ts

**Files:**
- Modify: `frontend/app/lib/api.ts`

- [ ] **Step 1: Add new TypeScript interfaces**

Add after the `BudgetStatus` interface in `frontend/app/lib/api.ts`:
```typescript
export interface FintocAccount {
  id: string;       // fintoc_account_id
  name: string;     // e.g. "Cuenta Corriente"
  type: string;     // e.g. "checking_account" | "credit_card"
  number: string;   // e.g. "****1234"
  currency: string;
}

export interface SelectedFintocAccount {
  fintoc_account_id: string;
  label: "personal" | "partner" | "joint";
}

export interface ConnectFintocPayload {
  link_token: string;
  household_id: string;
  accounts: SelectedFintocAccount[];
}

export interface ConnectFintocResult {
  created: number;
  accounts: Array<{ id: string; fintoc_account_id: string; account_type: string }>;
}

export interface ImportStatus {
  importing: boolean;
}
```

- [ ] **Step 2: Add new API methods to the api object**

Add inside the `api` object in `frontend/app/lib/api.ts`:
```typescript
  getFintocAccounts: (linkToken: string) =>
    apiFetch<FintocAccount[]>(
      `/bank-accounts/fintoc/accounts?link_token=${encodeURIComponent(linkToken)}`
    ),

  connectFintocAccounts: (payload: ConnectFintocPayload) =>
    apiFetch<ConnectFintocResult>("/bank-accounts/fintoc/connect", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getImportStatus: (householdId: string) =>
    apiFetch<ImportStatus>(`/bank-accounts/import-status?household_id=${householdId}`),
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/lib/api.ts
git commit -m "feat: add Fintoc types and API methods (getFintocAccounts, connectFintocAccounts, getImportStatus)"
```

---

### Task 14: FintocAccountPicker component

**Files:**
- Create: `frontend/app/(dashboard)/components/FintocAccountPicker.tsx`

- [ ] **Step 1: Create the component**

`frontend/app/(dashboard)/components/FintocAccountPicker.tsx`:
```tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FintocAccount, SelectedFintocAccount } from "@/app/lib/api";

interface Props {
  accounts: FintocAccount[];
  onConfirm: (selected: SelectedFintocAccount[]) => void;
  loading: boolean;
}

const LABEL_OPTIONS: Array<{ value: SelectedFintocAccount["label"]; label: string }> = [
  { value: "personal", label: "Personal" },
  { value: "partner", label: "Pareja" },
  { value: "joint", label: "Compartida" },
];

const ACCOUNT_TYPE_LABELS: Record<string, string> = {
  checking_account: "Cuenta Corriente",
  credit_card: "Tarjeta de Crédito",
  saving_account: "Cuenta de Ahorro",
  vista_account: "Cuenta Vista",
};

export function FintocAccountPicker({ accounts, onConfirm, loading }: Props) {
  const [selections, setSelections] = useState<
    Record<string, { checked: boolean; label: SelectedFintocAccount["label"] }>
  >(
    Object.fromEntries(accounts.map((a) => [a.id, { checked: true, label: "personal" }]))
  );

  function toggleAccount(id: string) {
    setSelections((prev) => ({
      ...prev,
      [id]: { ...prev[id], checked: !prev[id].checked },
    }));
  }

  function setLabel(id: string, label: SelectedFintocAccount["label"]) {
    setSelections((prev) => ({
      ...prev,
      [id]: { ...prev[id], label },
    }));
  }

  function handleConfirm() {
    const selected = accounts
      .filter((a) => selections[a.id]?.checked)
      .map((a) => ({ fintoc_account_id: a.id, label: selections[a.id].label }));
    onConfirm(selected);
  }

  const anySelected = Object.values(selections).some((s) => s.checked);

  return (
    <div className="space-y-3">
      <p className="text-sm text-luka-muted">
        Selecciona las cuentas que quieres conectar y etiqueta cada una.
      </p>

      {accounts.map((account) => {
        const sel = selections[account.id];
        return (
          <div
            key={account.id}
            className={`rounded-lg border p-4 transition-colors ${
              sel?.checked ? "border-luka-primary bg-luka-light" : "border-gray-200 bg-white"
            }`}
          >
            <div className="flex items-start gap-3">
              <input
                type="checkbox"
                checked={sel?.checked ?? false}
                onChange={() => toggleAccount(account.id)}
                className="mt-1 h-4 w-4 accent-luka-primary"
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-luka-dark text-sm">{account.name}</span>
                  <Badge variant="secondary" className="text-xs">
                    {ACCOUNT_TYPE_LABELS[account.type] ?? account.type}
                  </Badge>
                  <span className="text-luka-muted text-xs">{account.number}</span>
                </div>

                {sel?.checked && (
                  <div className="flex gap-2 mt-2">
                    {LABEL_OPTIONS.map((opt) => (
                      <button
                        key={opt.value}
                        onClick={() => setLabel(account.id, opt.value)}
                        className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                          sel.label === opt.value
                            ? "bg-luka-primary text-white border-luka-primary"
                            : "bg-white text-luka-muted border-gray-200 hover:border-luka-primary"
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}

      <Button
        onClick={handleConfirm}
        disabled={!anySelected || loading}
        className="w-full bg-luka-primary text-white hover:bg-blue-700"
      >
        {loading ? "Conectando..." : "Confirmar cuentas"}
      </Button>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add "frontend/app/(dashboard)/components/FintocAccountPicker.tsx"
git commit -m "feat: FintocAccountPicker - account selection with personal/partner/joint labels"
```

---

## PHASE 2 — Agent C-V: Frontend Verification
> **Run after Agent C completes and merges. Separate agent with fresh context.**

### Task C-V: Verify frontend after api.ts + FintocAccountPicker

**Files:** Any files with TypeScript errors found during verification.

- [ ] **Step 1: Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1
```

If output is empty → TypeScript passes. If errors appear → read them carefully and fix each one before proceeding.

- [ ] **Step 2: Run build**

```bash
cd frontend && npm run build 2>&1
```

Expected: Build succeeds, all routes listed, no red errors. If build fails → read the full error output, identify the root cause, fix it.

- [ ] **Step 3: Common issues to check**

  - Missing `export` on new interfaces in `api.ts`
  - Import path errors in `FintocAccountPicker.tsx` (check `@/app/lib/api` resolves correctly)
  - `"use client"` directive missing if the component uses hooks
  - Unused import warnings that escalate to errors

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve TypeScript/build issues after api.ts and FintocAccountPicker"
```

If no issues found, skip the commit. Leave a note: "C-V: no issues found, baseline clean."

---

## PHASE 3 — Parallel Implementation
> **🚦 Start both agents simultaneously after ALL of Phase 2 is merged to main.**

---

## PHASE 3 — Agent D: connect-bank page rewrite
> **Task 15. Requires Phase 2 Agent A (backend) and Agent C (api.ts + FintocAccountPicker).**

### Task 15: Rewrite connect-bank onboarding page

**Files:**
- Modify: `frontend/app/(auth)/onboarding/connect-bank/page.tsx`

- [ ] **Step 1: Replace the file entirely**

`frontend/app/(auth)/onboarding/connect-bank/page.tsx`:
```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Script from "next/script";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FintocAccountPicker } from "@/app/(dashboard)/components/FintocAccountPicker";
import { api, FintocAccount, SelectedFintocAccount } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";

declare global {
  interface Window {
    Fintoc?: {
      create: (options: {
        publicKey: string;
        product: string;
        country: string;
        onSuccess: (linkToken: string) => void;
        onExit: () => void;
        onError: (err: Error) => void;
      }) => { open: () => void };
    };
  }
}

type Step = "connect" | "pick" | "loading" | "done";

export default function ConnectBankPage() {
  const router = useRouter();
  const { householdId } = useLukaStore();
  const [step, setStep] = useState<Step>("connect");
  const [fintocAccounts, setFintocAccounts] = useState<FintocAccount[]>([]);
  const [linkToken, setLinkToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [scriptReady, setScriptReady] = useState(false);

  function openFintocWidget() {
    if (!window.Fintoc) {
      setError("Widget no disponible. Recarga la página.");
      return;
    }
    setError(null);
    const widget = window.Fintoc.create({
      publicKey: process.env.NEXT_PUBLIC_FINTOC_PUBLIC_KEY ?? "",
      product: "movements",
      country: "cl",
      onSuccess: async (token: string) => {
        setLinkToken(token);
        try {
          const accounts = await api.getFintocAccounts(token);
          setFintocAccounts(accounts);
          setStep("pick");
        } catch {
          setError("No se pudieron cargar las cuentas. Intenta de nuevo.");
        }
      },
      onExit: () => setError("Conexión cancelada."),
      onError: () => setError("Error al conectar. Intenta de nuevo."),
    });
    widget.open();
  }

  async function handleConfirm(selected: SelectedFintocAccount[]) {
    if (!householdId) return;
    setStep("loading");
    try {
      await api.connectFintocAccounts({
        link_token: linkToken,
        household_id: householdId,
        accounts: selected,
      });
      setStep("done");
      setTimeout(() => router.push("/onboarding/verify-whatsapp"), 1500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "";
      setError(
        msg.includes("409")
          ? "Una de las cuentas ya está conectada."
          : "Error al guardar las cuentas. Intenta de nuevo."
      );
      setStep("pick");
    }
  }

  return (
    <>
      <Script src="https://js.fintoc.com/v1/" onReady={() => setScriptReady(true)} />
      <div className="min-h-screen bg-luka-light flex items-center justify-center p-4">
        <Card className="w-full max-w-lg shadow-sm">
          <CardHeader>
            <CardTitle className="text-luka-dark">Conecta tu banco</CardTitle>
            <CardDescription className="text-luka-muted">
              Conecta tus cuentas bancarias y tarjetas. Importaremos los últimos 3 meses automáticamente.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {error && (
              <p className="text-sm text-luka-danger bg-red-50 rounded-md px-3 py-2">{error}</p>
            )}

            {step === "connect" && (
              <div className="space-y-4">
                <div className="rounded-lg bg-blue-50 border border-blue-100 p-4">
                  <p className="text-sm text-luka-dark font-medium mb-1">¿Cómo funciona?</p>
                  <ul className="text-sm text-luka-muted space-y-1 list-disc list-inside">
                    <li>Conecta de forma segura con tu banco</li>
                    <li>Elige qué cuentas y tarjetas incluir</li>
                    <li>Importamos 3 meses de historial automáticamente</li>
                  </ul>
                </div>
                <Button
                  onClick={openFintocWidget}
                  disabled={!scriptReady}
                  className="w-full bg-luka-primary text-white hover:bg-blue-700"
                >
                  {scriptReady ? "Conectar banco" : "Cargando..."}
                </Button>
                <button
                  onClick={() => router.push("/onboarding/verify-whatsapp")}
                  className="w-full text-sm text-luka-muted hover:text-luka-dark text-center"
                >
                  Saltar por ahora
                </button>
              </div>
            )}

            {step === "pick" && fintocAccounts.length > 0 && (
              <FintocAccountPicker
                accounts={fintocAccounts}
                onConfirm={handleConfirm}
                loading={false}
              />
            )}

            {step === "loading" && (
              <div className="text-center py-8">
                <p className="text-luka-dark font-medium">Guardando cuentas...</p>
                <p className="text-sm text-luka-muted mt-1">El historial se importará en segundo plano.</p>
              </div>
            )}

            {step === "done" && (
              <div className="text-center py-8">
                <p className="text-luka-dark font-medium">¡Cuentas conectadas!</p>
                <p className="text-sm text-luka-muted mt-1">Importando historial... Redirigiendo.</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add "frontend/app/(auth)/onboarding/connect-bank/page.tsx"
git commit -m "feat: rewrite connect-bank page with Fintoc Link widget and account picker"
```

---

## PHASE 3 — Agent D-V: Frontend Verification
> **Run after Agent D completes and merges. Separate agent with fresh context.**

### Task D-V: Verify frontend after connect-bank page rewrite

- [ ] **Step 1: Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1
```

Fix any errors before continuing.

- [ ] **Step 2: Run build**

```bash
cd frontend && npm run build 2>&1
```

Expected: All routes still appear in the output, including `/onboarding/connect-bank`. If the route disappears or shows an error, read the full build log.

- [ ] **Step 3: Common issues to check**

  - `window.Fintoc` type declaration conflicts — ensure the `declare global` block compiles
  - `Script` from `next/script` is a server-side import; the page must be `"use client"` (it is — verify)
  - `NEXT_PUBLIC_FINTOC_PUBLIC_KEY` missing from `.env.local` causes no TS error but widget will silently fail — acceptable for now, noted
  - Props type mismatch when passing `onConfirm` to `FintocAccountPicker`

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve TypeScript/build issues after connect-bank page rewrite"
```

---

## PHASE 3 — Agent E: Status Banner + Settings
> **Tasks 16–19. Requires Phase 2 Agent C (api.ts). Independent from Agent D.**

### Task 16: useImportStatus polling hook

**Files:**
- Create: `frontend/app/lib/hooks/useImportStatus.ts`

- [ ] **Step 1: Create the hook**

`frontend/app/lib/hooks/useImportStatus.ts`:
```typescript
"use client";

import { useEffect, useState } from "react";
import { api } from "@/app/lib/api";

const POLL_INTERVAL_MS = 5000;

export function useImportStatus(householdId: string | null) {
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    if (!householdId) return;

    let active = true;
    let timeoutId: ReturnType<typeof setTimeout>;

    async function poll() {
      try {
        const { importing: isImporting } = await api.getImportStatus(householdId!);
        if (!active) return;
        setImporting(isImporting);
        if (isImporting) {
          timeoutId = setTimeout(poll, POLL_INTERVAL_MS);
        }
      } catch {
        if (active) {
          timeoutId = setTimeout(poll, POLL_INTERVAL_MS);
        }
      }
    }

    poll();
    return () => {
      active = false;
      clearTimeout(timeoutId);
    };
  }, [householdId]);

  return { importing };
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/lib/hooks/useImportStatus.ts
git commit -m "feat: useImportStatus hook - polls import-status every 5s while importing"
```

---

### Task 17: ImportStatusBanner component

**Files:**
- Create: `frontend/app/(dashboard)/components/ImportStatusBanner.tsx`

- [ ] **Step 1: Create the component**

`frontend/app/(dashboard)/components/ImportStatusBanner.tsx`:
```tsx
"use client";

import { useImportStatus } from "@/app/lib/hooks/useImportStatus";
import { useLukaStore } from "@/app/lib/store";

export function ImportStatusBanner() {
  const { householdId } = useLukaStore();
  const { importing } = useImportStatus(householdId);

  if (!importing) return null;

  return (
    <div className="bg-blue-50 border-b border-blue-100 px-4 py-2 text-sm text-luka-primary flex items-center gap-2">
      <span className="inline-block h-2 w-2 rounded-full bg-luka-primary animate-pulse" />
      Importando historial de transacciones — esto puede tomar un momento.
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add "frontend/app/(dashboard)/components/ImportStatusBanner.tsx"
git commit -m "feat: ImportStatusBanner - shows while Fintoc history import is in progress"
```

---

### Task 18: Add banner to dashboard layout

**Files:**
- Modify: `frontend/app/(dashboard)/layout.tsx`

- [ ] **Step 1: Update the layout**

Replace the full content of `frontend/app/(dashboard)/layout.tsx`:
```tsx
import { Sidebar } from "./components/Sidebar";
import { BottomNav } from "./components/BottomNav";
import { StoreInitializer } from "./components/StoreInitializer";
import { InactivityGuard } from "./components/InactivityGuard";
import { ImportStatusBanner } from "./components/ImportStatusBanner";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-luka-surface">
      <StoreInitializer />
      <InactivityGuard />
      {/* Sidebar — desktop only */}
      <Sidebar />
      {/* Main scrolling area */}
      <main className="flex-1 overflow-y-auto pb-20 lg:pb-0">
        <ImportStatusBanner />
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
          {children}
        </div>
      </main>
      {/* Bottom nav — mobile only */}
      <BottomNav />
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add "frontend/app/(dashboard)/layout.tsx"
git commit -m "feat: add ImportStatusBanner to dashboard layout"
```

---

### Task 19: Settings page — Add Account button

**Files:**
- Modify: `frontend/app/(dashboard)/settings/page.tsx`

**Note on scope:** `HouseholdSummaryRow` does not include `bank_accounts`. Rather than adding a new list endpoint (deferred to a future task), this task adds only an "Add Account" button that opens the Fintoc widget. Listing connected accounts in settings is a follow-up task.

- [ ] **Step 1: Read the current settings page**

Read `frontend/app/(dashboard)/settings/page.tsx` to understand the existing structure before editing.

- [ ] **Step 2: Add imports and the ConnectBankSection component**

At the top of the file, add the necessary imports for Fintoc:
```tsx
import Script from "next/script";
import { useState } from "react";
import { api, FintocAccount, SelectedFintocAccount } from "@/app/lib/api";
import { FintocAccountPicker } from "@/app/(dashboard)/components/FintocAccountPicker";
```

Add this component definition before the default export:
```tsx
function ConnectBankSection() {
  const { householdId } = useLukaStore();
  const [scriptReady, setScriptReady] = useState(false);
  const [showPicker, setShowPicker] = useState(false);
  const [fintocAccounts, setFintocAccounts] = useState<FintocAccount[]>([]);
  const [linkToken, setLinkToken] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  function openWidget() {
    if (!window.Fintoc) return;
    setMessage(null);
    const widget = window.Fintoc.create({
      publicKey: process.env.NEXT_PUBLIC_FINTOC_PUBLIC_KEY ?? "",
      product: "movements",
      country: "cl",
      onSuccess: async (token: string) => {
        setLinkToken(token);
        const accounts = await api.getFintocAccounts(token);
        setFintocAccounts(accounts);
        setShowPicker(true);
      },
      onExit: () => setMessage("Conexión cancelada."),
      onError: () => setMessage("Error al conectar."),
    });
    widget.open();
  }

  async function handleConfirm(selected: SelectedFintocAccount[]) {
    if (!householdId) return;
    setConnecting(true);
    try {
      await api.connectFintocAccounts({ link_token: linkToken, household_id: householdId, accounts: selected });
      setShowPicker(false);
      setFintocAccounts([]);
      setMessage("¡Cuentas conectadas! El historial se importa en segundo plano.");
    } catch {
      setMessage("Error al guardar las cuentas.");
    } finally {
      setConnecting(false);
    }
  }

  return (
    <>
      <Script src="https://js.fintoc.com/v1/" onReady={() => setScriptReady(true)} />
      <Card className="shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base text-luka-dark">Cuentas bancarias</CardTitle>
          {!showPicker && (
            <Button
              size="sm"
              variant="outline"
              onClick={openWidget}
              disabled={!scriptReady}
              className="text-luka-primary border-luka-primary hover:bg-luka-light"
            >
              + Agregar cuenta
            </Button>
          )}
        </CardHeader>
        <CardContent>
          {message && <p className="text-sm text-luka-muted mb-3">{message}</p>}
          {showPicker && (
            <FintocAccountPicker
              accounts={fintocAccounts}
              onConfirm={handleConfirm}
              loading={connecting}
            />
          )}
          {!showPicker && !message && (
            <p className="text-sm text-luka-muted">
              Conecta tus cuentas para importar transacciones automáticamente.
            </p>
          )}
        </CardContent>
      </Card>
    </>
  );
}
```

Render `<ConnectBankSection />` in the settings page JSX, above the existing account/privacy cards.

- [ ] **Step 3: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add "frontend/app/(dashboard)/settings/page.tsx"
git commit -m "feat: add Connect Bank section to settings page"
```

---

## PHASE 3 — Agent E-V: Frontend Verification
> **Run after Agent E completes and merges. Separate agent with fresh context.**

### Task E-V: Verify frontend after banner + settings

- [ ] **Step 1: Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1
```

Fix any errors before continuing.

- [ ] **Step 2: Run build**

```bash
cd frontend && npm run build 2>&1
```

Expected: All 14 original routes still present plus any new ones. No build failures.

- [ ] **Step 3: Common issues to check**

  - `ImportStatusBanner` imports `useImportStatus` — verify hook path resolves
  - `useImportStatus` uses `useState`/`useEffect` — verify `"use client"` directive is present in the hook file (it is — double-check)
  - `ConnectBankSection` in settings imports `FintocAccountPicker` from dashboard components — this cross-route-group import is valid in Next.js App Router but verify the path `@/app/(dashboard)/components/FintocAccountPicker` resolves correctly. If it doesn't, move the component to `@/app/components/` and update all imports.
  - `Script` component from `next/script` used inside a Client Component in settings — valid, but check for SSR warnings

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve TypeScript/build issues after banner and settings"
```

---

## PHASE 4 — Integration
> **One agent. Run after Phase 3 is fully merged. Requires all previous phases.**

### Task 20: Wire worker, run migrations, smoke test

**Files:**
- Modify: `backend/worker.py`

- [ ] **Step 1: Update worker.py — add import_fintoc_history**

The `import_fintoc_history` function now exists (written in Task 11). Update `backend/worker.py`:

```python
import redis.asyncio as aioredis
from arq import cron
from arq.connections import RedisSettings
from core.config import settings
from jobs.tasks import (
    process_email,
    import_fintoc_history,
    renew_mail_watches,
    purge_raw_emails,
    cleanup_processed_webhooks,
    run_fintoc_sync,
)


async def startup(ctx: dict) -> None:
    ctx["redis"] = await aioredis.from_url(settings.redis_url)


async def shutdown(ctx: dict) -> None:
    await ctx["redis"].aclose()


class WorkerSettings:
    functions = [process_email, import_fintoc_history]
    cron_jobs = [
        cron(renew_mail_watches, hour=3, minute=0),   # 3am daily
        cron(purge_raw_emails, minute=0),              # every hour
        cron(cleanup_processed_webhooks, hour=4, minute=0),  # 4am daily
        cron(run_fintoc_sync, hour=2, minute=0),       # 2am nightly
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 60
```

- [ ] **Step 2: Verify worker loads**

```bash
cd backend && python -c "from worker import WorkerSettings; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Run full backend test suite**

```bash
cd backend && python -m pytest tests/ -v
```
Expected: All tests pass.

- [ ] **Step 4: Verify frontend builds**

```bash
cd frontend && npm run build
```
Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 5: Run migrations on local DB**

```bash
cd backend && alembic upgrade head
```
Expected: Ends with `Running upgrade 004 -> 005, Add import_status column to bank_accounts`

- [ ] **Step 6: Verify routes are registered**

```bash
cd backend && python -c "
from main import app
routes = [r.path for r in app.routes]
assert '/bank-accounts/fintoc/accounts' in routes
assert '/bank-accounts/fintoc/connect' in routes
assert '/bank-accounts/import-status' in routes
print('All routes registered OK')
"
```

- [ ] **Step 7: Add env var to Vercel**

In Vercel dashboard → Settings → Environment Variables:
- Name: `NEXT_PUBLIC_FINTOC_PUBLIC_KEY`
- Value: your Fintoc public key (from fintoc.com dashboard → Settings → API Keys)
- Environments: Production + Preview

- [ ] **Step 8: Run migrations on production DB**

```bash
cd backend && DATABASE_URL=<production_url> alembic upgrade head
```

- [ ] **Step 9: Commit and deploy**

```bash
git add backend/worker.py
git commit -m "feat: register import_fintoc_history in ARQ worker"
git push origin main
```
Railway and Vercel auto-deploy on push to main.

---

## Parallel Execution Cheatsheet

```
PHASE 1 (one agent):
  git checkout -b feat/fintoc-foundation
  → Tasks 1, 2, 3, 4 in order → merge to main

PHASE 2 (four simultaneous agents from main):
  Agent A:   git checkout -b feat/fintoc-backend-routes      → Tasks 5–9
  Agent B:   git checkout -b feat/fintoc-import-job          → Tasks 10–12
  Agent C:   git checkout -b feat/fintoc-frontend-foundation → Tasks 13–14 → merge
  Agent C-V: git checkout -b fix/fintoc-frontend-c-verify    → Task C-V (after C merges)
  → All four done before Phase 3

PHASE 3 (four simultaneous agents from main):
  Agent D:   git checkout -b feat/fintoc-connect-page        → Task 15 → merge
  Agent D-V: git checkout -b fix/fintoc-frontend-d-verify    → Task D-V (after D merges)
  Agent E:   git checkout -b feat/fintoc-status-settings     → Tasks 16–19 → merge
  Agent E-V: git checkout -b fix/fintoc-frontend-e-verify    → Task E-V (after E merges)
  → All four done before Phase 4

PHASE 4 (one agent):
  git checkout -b feat/fintoc-integration
  → Task 20 → merge to main → push → deploy
```
