# Fintoc Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the manual bank account form with Fintoc Link widget, auto-import 90 days of transaction history on connect, and track import progress with a dashboard banner.

**Architecture:** Fintoc JS widget runs in-browser and returns a `link_token`. Backend fetches account list from Fintoc API using that token and returns it to the frontend for user selection. On confirm, backend creates `BankAccount` records and enqueues one `import_fintoc_history` ARQ job per account, which fetches 90 days of transactions and inserts them as settled+uncategorized with auto-assigned splits.

**Tech Stack:** FastAPI + SQLAlchemy async + ARQ + httpx (backend) | Next.js App Router + Tailwind + shadcn/ui (frontend) | Fintoc JS SDK

**Spec:** `docs/superpowers/specs/2026-03-18-fintoc-integration-design.md`

---

## Execution Map

```
PHASE 1 (sequential): Tasks 1–5   ← foundation, everything depends on this
    ↓
PHASE 2 (3 parallel agents):
    Agent A: Tasks 6–10  ← backend routes
    Agent B: Tasks 11–13 ← backend import job
    Agent C: Tasks 14–15 ← frontend foundation (api.ts + FintocAccountPicker)
    ↓ (all three must complete)
PHASE 3 (2 parallel agents):
    Agent D: Task 16     ← connect-bank page rewrite
    Agent E: Tasks 17–20 ← status banner + settings
    ↓
PHASE 4 (sequential): Task 21    ← migrations + smoke test
```

---

## PHASE 1 — Foundation
> **One agent. Run sequentially. All later phases depend on this.**

### Task 1: Migration 004 — Enforce valid account_type values

**Files:**
- Create: `backend/alembic/versions/004_account_type_constraint.py`

- [ ] **Step 1: Write the migration**

```python
"""Enforce account_type IN ('personal', 'partner', 'joint').

Revision ID: 004
Down revision: 003
"""
import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"


def upgrade():
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

- [ ] **Step 1: Update the BankAccount class**

In `backend/modules/households/models.py`, update the `BankAccount` class. Change line 48 and add `import_status` after `is_active`:

Old:
```python
    account_type: Mapped[str] = mapped_column(String, nullable=False)  # 'personal' | 'joint'
```

New:
```python
    account_type: Mapped[str] = mapped_column(String, nullable=False)  # 'personal' | 'partner' | 'joint'
```

Add after `is_active` (line 53):
```python
    import_status: Mapped[str] = mapped_column(String, default="done")  # 'pending'|'importing'|'done'|'failed'
```

- [ ] **Step 2: Verify the model compiles**

```bash
cd backend && python -c "from modules.households.models import BankAccount; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/modules/households/models.py
git commit -m "feat: add import_status to BankAccount model, add partner account_type"
```

---

### Task 4: Create bank_accounts module and register in main.py

**Files:**
- Create: `backend/modules/bank_accounts/__init__.py`
- Create: `backend/modules/bank_accounts/router.py` (skeleton)
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

In `backend/main.py`, add after the existing imports:
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
git commit -m "feat: add bank_accounts module and register router at /bank-accounts"
```

---

### Task 5: Register import_fintoc_history in worker

**Files:**
- Modify: `backend/worker.py`

- [ ] **Step 1: Add import to worker.py**

In `backend/worker.py`, update the import line:
```python
from jobs.tasks import (
    process_email,
    import_fintoc_history,
    renew_mail_watches,
    purge_raw_emails,
    cleanup_processed_webhooks,
    run_fintoc_sync,
)
```

And add `import_fintoc_history` to the `functions` list:
```python
class WorkerSettings:
    functions = [process_email, import_fintoc_history]
```

The function doesn't exist yet — this import will fail until Task 12 is done. That's fine: Phase 2 Agent B writes the job, Phase 4 runs everything together.

- [ ] **Step 2: Commit**

```bash
git add backend/worker.py
git commit -m "feat: register import_fintoc_history in ARQ worker functions"
```

---

## PHASE 2 — Parallel Implementation
> **🚦 Start all three agents simultaneously after Phase 1 is merged.**

---

## PHASE 2 — Agent A: Backend Routes
> **Tasks 6–10. Does NOT depend on Agent B or C.**

### Task 6: Add fetch_accounts to FintocClient

**Files:**
- Modify: `backend/modules/fintoc/client.py`

- [ ] **Step 1: Write a failing test**

Create `backend/tests/test_fintoc_client_accounts.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from modules.fintoc.client import FintocClient


@pytest.mark.asyncio
async def test_fetch_accounts_returns_account_list():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {
            "id": "acc_123",
            "name": "Cuenta Corriente",
            "type": "checking_account",
            "number": "****1234",
            "currency": "CLP",
        },
        {
            "id": "acc_456",
            "name": "Tarjeta de Crédito",
            "type": "credit_card",
            "number": "****5678",
            "currency": "CLP",
        },
    ]
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        client = FintocClient(link_token="lt_test")
        accounts = await client.fetch_accounts()

    assert len(accounts) == 2
    assert accounts[0]["id"] == "acc_123"
    assert accounts[1]["type"] == "credit_card"
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd backend && python -m pytest tests/test_fintoc_client_accounts.py -v
```
Expected: `AttributeError: 'FintocClient' object has no attribute 'fetch_accounts'`

- [ ] **Step 3: Implement fetch_accounts in FintocClient**

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

- [ ] **Step 4: Run test — expect PASS**

```bash
cd backend && python -m pytest tests/test_fintoc_client_accounts.py -v
```
Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/modules/fintoc/client.py backend/tests/test_fintoc_client_accounts.py
git commit -m "feat: add FintocClient.fetch_accounts()"
```

---

### Task 7: GET /bank-accounts/fintoc/accounts endpoint

**Files:**
- Modify: `backend/modules/bank_accounts/router.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_bank_accounts_routes.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_get_fintoc_accounts_returns_list(client, auth_headers):
    mock_accounts = [
        {"id": "acc_1", "name": "Cuenta Corriente", "type": "checking_account", "number": "****1234"},
    ]
    with patch("modules.bank_accounts.router.FintocClient") as MockClient:
        instance = AsyncMock()
        instance.fetch_accounts = AsyncMock(return_value=mock_accounts)
        MockClient.return_value = instance

        response = await client.get(
            "/bank-accounts/fintoc/accounts?link_token=lt_test",
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert response.json() == mock_accounts


@pytest.mark.asyncio
async def test_get_fintoc_accounts_requires_auth(client):
    response = await client.get("/bank-accounts/fintoc/accounts?link_token=lt_test")
    assert response.status_code == 401
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
    """Fetch available Fintoc accounts for a link token. Called after widget success."""
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
git commit -m "feat: GET /bank-accounts/fintoc/accounts - fetch account list for link token"
```

---

### Task 8: POST /bank-accounts/fintoc/connect endpoint

**Files:**
- Modify: `backend/modules/bank_accounts/router.py`
- Modify: `backend/tests/test_bank_accounts_routes.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_bank_accounts_routes.py`:
```python
@pytest.mark.asyncio
async def test_connect_fintoc_returns_403_if_not_member(client, auth_headers):
    response = await client.post(
        "/bank-accounts/fintoc/connect",
        json={
            "link_token": "lt_test",
            "household_id": "00000000-0000-0000-0000-000000000001",
            "accounts": [{"fintoc_account_id": "acc_1", "label": "personal"}],
        },
        headers=auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_connect_fintoc_creates_accounts_and_enqueues_jobs(
    client, auth_headers, test_db, test_user, test_household
):
    with patch("modules.bank_accounts.router.enqueue_job") as mock_enqueue:
        mock_enqueue.return_value = None
        response = await client.post(
            "/bank-accounts/fintoc/connect",
            json={
                "link_token": "lt_abc",
                "household_id": str(test_household.id),
                "accounts": [
                    {"fintoc_account_id": "acc_1", "label": "personal"},
                    {"fintoc_account_id": "acc_2", "label": "joint"},
                ],
            },
            headers=auth_headers,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["created"] == 2
    assert mock_enqueue.call_count == 2


@pytest.mark.asyncio
async def test_connect_fintoc_returns_409_on_duplicate(
    client, auth_headers, test_db, test_household, existing_fintoc_account
):
    response = await client.post(
        "/bank-accounts/fintoc/connect",
        json={
            "link_token": "lt_abc",
            "household_id": str(test_household.id),
            "accounts": [
                {"fintoc_account_id": existing_fintoc_account.fintoc_account_id, "label": "personal"}
            ],
        },
        headers=auth_headers,
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
    """Store Fintoc-connected accounts and enqueue 90-day history import."""
    await _require_household_membership(body.household_id, current_user.id, db)

    # Check for duplicates
    for acct in body.accounts:
        existing = await db.scalar(
            select(BankAccount).where(
                BankAccount.fintoc_account_id == acct.fintoc_account_id
            )
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Account {acct.fintoc_account_id} is already connected",
            )

    # Create bank accounts and enqueue import job per account
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
        await db.flush()  # get the id before commit
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
async def test_import_status_returns_403_if_not_member(client, auth_headers):
    response = await client.get(
        "/bank-accounts/import-status?household_id=00000000-0000-0000-0000-000000000001",
        headers=auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_import_status_true_when_accounts_pending(
    client, auth_headers, test_household, pending_bank_account
):
    response = await client.get(
        f"/bank-accounts/import-status?household_id={test_household.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json() == {"importing": True}


@pytest.mark.asyncio
async def test_import_status_false_when_all_done(
    client, auth_headers, test_household, done_bank_account
):
    response = await client.get(
        f"/bank-accounts/import-status?household_id={test_household.id}",
        headers=auth_headers,
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

- [ ] **Step 4: Run — expect PASS**

```bash
cd backend && python -m pytest tests/test_bank_accounts_routes.py -v
```
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/bank_accounts/router.py backend/tests/test_bank_accounts_routes.py
git commit -m "feat: GET /bank-accounts/import-status - poll household import progress"
```

---

## PHASE 2 — Agent B: Backend Import Job
> **Tasks 11–13. Does NOT depend on Agent A or C.**

### Task 11: Add enqueue helper to queue.py

**Files:**
- Modify: `backend/jobs/queue.py`

- [ ] **Step 1: Add the typed helper**

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
git commit -m "feat: add enqueue_fintoc_history_import helper"
```

---

### Task 12: import_fintoc_history ARQ job

**Files:**
- Modify: `backend/jobs/tasks.py`

- [ ] **Step 1: Write the failing test first**

Create `backend/tests/test_fintoc_import.py`:
```python
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from modules.fintoc.client import FintocTransaction


def make_fintoc_txn(id: str, amount: int, description: str) -> FintocTransaction:
    return FintocTransaction(
        id=id,
        amount=amount,
        description=description,
        transaction_date=datetime(2026, 1, 15, tzinfo=timezone.utc),
        account_id="acc_test",
    )


@pytest.mark.asyncio
async def test_import_creates_transactions_and_splits():
    """Happy path: two Fintoc transactions become two DB transactions with splits."""
    from jobs.tasks import import_fintoc_history

    mock_account = MagicMock()
    mock_account.id = "ba_1"
    mock_account.fintoc_link_id = "lt_test"
    mock_account.fintoc_account_id = "acc_test"
    mock_account.account_type = "personal"
    mock_account.user_id = "user_1"
    mock_account.household_id = "hh_1"

    fintoc_txns = [
        make_fintoc_txn("ft_1", 10000, "LIDER EXPRESS"),
        make_fintoc_txn("ft_2", 5000, "UBER"),
    ]

    with patch("jobs.tasks.AsyncSessionLocal") as MockSession, \
         patch("jobs.tasks.FintocClient") as MockClient:

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_account)
        mock_db.scalar = AsyncMock(return_value=None)  # no existing fintoc_id
        mock_db.commit = AsyncMock()
        mock_db.flush = AsyncMock()
        MockSession.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        MockSession.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_client_instance = AsyncMock()
        mock_client_instance.fetch_transactions = AsyncMock(return_value=fintoc_txns)
        MockClient.return_value = mock_client_instance

        await import_fintoc_history({}, bank_account_id="ba_1")

    # Two transactions + two splits added
    assert mock_db.add.call_count == 4
    # Status set to 'importing' then 'done'
    assert mock_account.import_status == "done"


@pytest.mark.asyncio
async def test_import_skips_existing_fintoc_id():
    """Idempotency: if fintoc_id already in DB, skip that transaction."""
    from jobs.tasks import import_fintoc_history

    mock_account = MagicMock()
    mock_account.id = "ba_1"
    mock_account.fintoc_link_id = "lt_test"
    mock_account.fintoc_account_id = "acc_test"
    mock_account.account_type = "personal"
    mock_account.user_id = "user_1"
    mock_account.household_id = "hh_1"

    fintoc_txns = [make_fintoc_txn("ft_already_exists", 10000, "COPEC")]

    with patch("jobs.tasks.AsyncSessionLocal") as MockSession, \
         patch("jobs.tasks.FintocClient") as MockClient:

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_account)
        mock_db.scalar = AsyncMock(return_value=MagicMock())  # existing txn found
        mock_db.commit = AsyncMock()
        MockSession.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        MockSession.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_client_instance = AsyncMock()
        mock_client_instance.fetch_transactions = AsyncMock(return_value=fintoc_txns)
        MockClient.return_value = mock_client_instance

        await import_fintoc_history({}, bank_account_id="ba_1")

    # Nothing added (skipped)
    mock_db.add.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("account_type,expected_split", [
    ("personal", "personal"),
    ("partner", "partner"),
    ("joint", "shared"),
])
async def test_import_split_type_mapping(account_type, expected_split):
    """Account label correctly maps to split_type."""
    from jobs.tasks import import_fintoc_history
    from modules.transactions.models import TransactionSplit

    mock_account = MagicMock()
    mock_account.id = "ba_1"
    mock_account.fintoc_link_id = "lt_test"
    mock_account.fintoc_account_id = "acc_test"
    mock_account.account_type = account_type
    mock_account.user_id = "user_1"
    mock_account.household_id = "hh_1"

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

        mock_client_instance = AsyncMock()
        mock_client_instance.fetch_transactions = AsyncMock(
            return_value=[make_fintoc_txn("ft_1", 5000, "JUMBO")]
        )
        MockClient.return_value = mock_client_instance

        await import_fintoc_history({}, bank_account_id="ba_1")

    splits = [o for o in added_objects if isinstance(o, TransactionSplit)]
    assert len(splits) == 1
    assert splits[0].split_type == expected_split


@pytest.mark.asyncio
async def test_import_sets_status_failed_on_error():
    """On Fintoc API error, import_status is set to 'failed' and job logged."""
    from jobs.tasks import import_fintoc_history

    mock_account = MagicMock()
    mock_account.id = "ba_1"
    mock_account.fintoc_link_id = "lt_test"
    mock_account.fintoc_account_id = "acc_test"
    mock_account.account_type = "personal"
    mock_account.user_id = "user_1"
    mock_account.household_id = "hh_1"

    with patch("jobs.tasks.AsyncSessionLocal") as MockSession, \
         patch("jobs.tasks.FintocClient") as MockClient:

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_account)
        mock_db.commit = AsyncMock()
        MockSession.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        MockSession.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_client_instance = AsyncMock()
        mock_client_instance.fetch_transactions = AsyncMock(
            side_effect=Exception("Fintoc API down")
        )
        MockClient.return_value = mock_client_instance

        await import_fintoc_history({}, bank_account_id="ba_1")

    assert mock_account.import_status == "failed"
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd backend && python -m pytest tests/test_fintoc_import.py -v
```
Expected: `ImportError` or `AttributeError` (function doesn't exist yet)

- [ ] **Step 3: Implement the job in tasks.py**

Add to `backend/jobs/tasks.py` (after the existing imports, add `from date import date, timedelta` is already imported — add the new imports):

First, add to the imports block at the top of the file:
```python
from modules.fintoc.client import FintocClient
from modules.transactions.models import Transaction, TransactionSplit, ProcessedWebhook, FailedJob
```
(Note: `Transaction`, `TransactionSplit`, `FailedJob` are already imported — just add `FintocClient`)

Then add the new job function:
```python
async def import_fintoc_history(ctx: dict, bank_account_id: str) -> None:
    """
    One-shot job: import 90 days of Fintoc transactions for a bank account.
    Runs automatically when a user connects a bank account via Fintoc Link.
    Idempotent: skips transactions already in DB by fintoc_id.
    """
    from datetime import date, timedelta, timezone

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

            split_map = {
                "personal": "personal",
                "partner": "partner",
                "joint": "shared",
            }

            imported = 0
            skipped = 0

            for ftxn in fintoc_txns:
                # Idempotency: skip if already imported
                existing = await db.scalar(
                    select(Transaction).where(Transaction.fintoc_id == ftxn.id)
                )
                if existing:
                    skipped += 1
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
                imported += 1

            await db.commit()
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

### Task 13: Run full backend test suite

- [ ] **Step 1: Run all tests**

```bash
cd backend && python -m pytest tests/ -v
```
Expected: All existing tests still pass + new tests pass. No regressions.

- [ ] **Step 2: Commit if any fixes were needed**

```bash
git add -A && git commit -m "fix: resolve any test conflicts after fintoc import job"
```

---

## PHASE 2 — Agent C: Frontend Foundation
> **Tasks 14–15. Does NOT depend on Agent A or B.**

### Task 14: Add Fintoc types and API methods to api.ts

**Files:**
- Modify: `frontend/app/lib/api.ts`

- [ ] **Step 1: Add new TypeScript interfaces**

Add after the existing `BudgetStatus` interface in `frontend/app/lib/api.ts`:
```typescript
export interface FintocAccount {
  id: string;          // fintoc_account_id
  name: string;        // e.g. "Cuenta Corriente"
  type: string;        // e.g. "checking_account" | "credit_card"
  number: string;      // e.g. "****1234"
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

- [ ] **Step 2: Add new API methods**

Add to the `api` object in `frontend/app/lib/api.ts`:
```typescript
  getFintocAccounts: (linkToken: string) =>
    apiFetch<FintocAccount[]>(`/bank-accounts/fintoc/accounts?link_token=${encodeURIComponent(linkToken)}`),

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
git commit -m "feat: add Fintoc types and API methods to api.ts"
```

---

### Task 15: FintocAccountPicker component

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
    Object.fromEntries(
      accounts.map((a) => [a.id, { checked: true, label: "personal" }])
    )
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
      .map((a) => ({
        fintoc_account_id: a.id,
        label: selections[a.id].label,
      }));
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
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/(dashboard)/components/FintocAccountPicker.tsx
git commit -m "feat: FintocAccountPicker component - account selection with personal/partner/joint labels"
```

---

## PHASE 3 — Parallel Implementation
> **🚦 Start both agents simultaneously after ALL of Phase 2 completes.**

---

## PHASE 3 — Agent D: connect-bank page rewrite
> **Task 16. Requires Phase 2 Agent A (backend endpoints) and Agent C (api.ts + FintocAccountPicker).**

### Task 16: Rewrite connect-bank onboarding page

**Files:**
- Modify: `frontend/app/(auth)/onboarding/connect-bank/page.tsx`

- [ ] **Step 1: Replace the file entirely**

`frontend/app/(auth)/onboarding/connect-bank/page.tsx`:
```tsx
"use client";

import { useEffect, useRef, useState } from "react";
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
  const [linkToken, setLinkToken] = useState<string>("");
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
          setStep("connect");
        }
      },
      onExit: () => {
        setError("Conexión cancelada.");
      },
      onError: () => {
        setError("Error al conectar. Intenta de nuevo.");
      },
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
      // Small delay so user sees success message before redirect
      setTimeout(() => router.push("/onboarding/verify-whatsapp"), 1500);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error desconocido";
      setError(
        message.includes("409")
          ? "Una de las cuentas ya está conectada."
          : "Error al guardar las cuentas. Intenta de nuevo."
      );
      setStep("pick");
    }
  }

  return (
    <>
      <Script
        src="https://js.fintoc.com/v1/"
        onReady={() => setScriptReady(true)}
      />

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
                <p className="text-sm text-luka-muted mt-1">
                  El historial se importará en segundo plano.
                </p>
              </div>
            )}

            {step === "done" && (
              <div className="text-center py-8">
                <p className="text-luka-dark font-medium">¡Cuentas conectadas!</p>
                <p className="text-sm text-luka-muted mt-1">
                  Importando historial... Redirigiendo.
                </p>
              </div>
            )}

            {step === "connect" && (
              <button
                onClick={() => router.push("/onboarding/verify-whatsapp")}
                className="w-full text-sm text-luka-muted hover:text-luka-dark text-center"
              >
                Saltar por ahora
              </button>
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
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add "frontend/app/(auth)/onboarding/connect-bank/page.tsx"
git commit -m "feat: rewrite connect-bank page with Fintoc Link widget and account picker"
```

---

## PHASE 3 — Agent E: Status Banner + Settings
> **Tasks 17–20. Requires Phase 2 Agent C (api.ts). Independent from Agent D.**

### Task 17: useImportStatus polling hook

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
        // Silently retry on error — banner stays visible
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
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/lib/hooks/useImportStatus.ts
git commit -m "feat: useImportStatus hook - polls /bank-accounts/import-status every 5s"
```

---

### Task 18: ImportStatusBanner component

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
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add "frontend/app/(dashboard)/components/ImportStatusBanner.tsx"
git commit -m "feat: ImportStatusBanner component - shows while Fintoc history is importing"
```

---

### Task 19: Add banner to dashboard layout

**Files:**
- Modify: `frontend/app/(dashboard)/layout.tsx`

- [ ] **Step 1: Update the layout**

In `frontend/app/(dashboard)/layout.tsx`, add the import and render the banner:

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

### Task 20: Settings page — Connected Accounts section

**Files:**
- Modify: `frontend/app/(dashboard)/settings/page.tsx`

- [ ] **Step 1: Read the current settings page**

Read `frontend/app/(dashboard)/settings/page.tsx` to understand the current structure before editing.

- [ ] **Step 2: Add Connected Accounts section**

Add at the top of the file, after the existing imports:
```tsx
"use client";

import { useState, useEffect } from "react";
import Script from "next/script";
import { useRouter } from "next/navigation";
import { createClient } from "@/app/lib/supabase/client";
import { useLukaStore } from "@/app/lib/store";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api, FintocAccount, SelectedFintocAccount } from "@/app/lib/api";
import { FintocAccountPicker } from "@/app/(dashboard)/components/FintocAccountPicker";
import { useHouseholdSummary } from "@/app/lib/hooks/useHousehold";
```

Add a `ConnectedAccountsCard` section inside the settings page component. Insert it before the existing account card:

```tsx
function ConnectedAccountsCard() {
  const { householdId } = useLukaStore();
  const { data: summary } = useHouseholdSummary(householdId ?? "");
  const [showPicker, setShowPicker] = useState(false);
  const [fintocAccounts, setFintocAccounts] = useState<FintocAccount[]>([]);
  const [linkToken, setLinkToken] = useState("");
  const [scriptReady, setScriptReady] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function openWidget() {
    if (!window.Fintoc) return;
    setError(null);
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
      onExit: () => setError("Conexión cancelada."),
      onError: () => setError("Error al conectar."),
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
    } catch {
      setError("Error al guardar las cuentas.");
    } finally {
      setConnecting(false);
    }
  }

  const bankAccounts = summary?.flatMap((row: { bank_accounts?: unknown[] }) => row.bank_accounts ?? []) ?? [];

  return (
    <>
      <Script src="https://js.fintoc.com/v1/" onReady={() => setScriptReady(true)} />
      <Card className="shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base text-luka-dark">Cuentas conectadas</CardTitle>
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
        <CardContent className="space-y-3">
          {error && (
            <p className="text-sm text-luka-danger">{error}</p>
          )}
          {bankAccounts.length === 0 && !showPicker && (
            <p className="text-sm text-luka-muted">No hay cuentas conectadas aún.</p>
          )}
          {bankAccounts.map((acct: Record<string, string>) => (
            <div key={acct.id} className="flex items-center justify-between py-2 border-b last:border-0">
              <div>
                <p className="text-sm font-medium text-luka-dark">{acct.bank_name}</p>
                {acct.fintoc_account_id && (
                  <p className="text-xs text-luka-muted">{acct.fintoc_account_id.slice(-8)}</p>
                )}
              </div>
              <Badge variant="secondary" className="text-xs capitalize">{acct.account_type}</Badge>
            </div>
          ))}
          {showPicker && (
            <FintocAccountPicker
              accounts={fintocAccounts}
              onConfirm={handleConfirm}
              loading={connecting}
            />
          )}
        </CardContent>
      </Card>
    </>
  );
}
```

Then render `<ConnectedAccountsCard />` at the top of the settings page JSX, before the existing account card.

- [ ] **Step 3: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add "frontend/app/(dashboard)/settings/page.tsx"
git commit -m "feat: add Connected Accounts section to settings page"
```

---

## PHASE 4 — Integration
> **One agent. Run after Phase 3 completes. Requires all previous phases merged.**

### Task 21: Run migrations, verify, document env vars

- [ ] **Step 1: Run migrations on local/staging DB**

```bash
cd backend && alembic upgrade head
```
Expected output ends with: `Running upgrade 004 -> 005, Add import_status column to bank_accounts`

- [ ] **Step 2: Verify all backend tests pass**

```bash
cd backend && python -m pytest tests/ -v
```
Expected: All tests pass, no regressions.

- [ ] **Step 3: Verify FastAPI starts and routes are registered**

```bash
cd backend && uvicorn main:app --reload &
curl http://localhost:8000/openapi.json | python -m json.tool | grep "bank-accounts"
kill %1
```
Expected: See `/bank-accounts/fintoc/accounts`, `/bank-accounts/fintoc/connect`, `/bank-accounts/import-status` in the output.

- [ ] **Step 4: Verify frontend builds**

```bash
cd frontend && npm run build
```
Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 5: Add env var to Vercel**

In Vercel dashboard → Settings → Environment Variables:
- Name: `NEXT_PUBLIC_FINTOC_PUBLIC_KEY`
- Value: your Fintoc public key (from fintoc.com dashboard)
- Environment: Production + Preview

- [ ] **Step 6: Add env var to Railway**

`FINTOC_API_KEY` is already set. Confirm it is the same key used in `FintocClient`.

- [ ] **Step 7: Run migrations on production DB**

```bash
cd backend && DATABASE_URL=<production_url> alembic upgrade head
```

- [ ] **Step 8: Final commit — update project state docs**

```bash
git add -A
git commit -m "feat: complete Fintoc integration - widget, history import, status banner"
```

- [ ] **Step 9: Deploy**

Push to `main`. Railway and Vercel auto-deploy.

```bash
git push origin main
```

---

## Parallel Execution Cheatsheet

```
PHASE 1 (one agent):
  git checkout -b feat/fintoc-foundation
  → Tasks 1, 2, 3, 4, 5 in order
  → Merge to main

PHASE 2 (three simultaneous agents from main):
  Agent A: git checkout -b feat/fintoc-backend-routes    → Tasks 6, 7, 8, 9, 10
  Agent B: git checkout -b feat/fintoc-import-job        → Tasks 11, 12, 13
  Agent C: git checkout -b feat/fintoc-frontend-foundation → Tasks 14, 15
  → All three merge to main when done

PHASE 3 (two simultaneous agents from main):
  Agent D: git checkout -b feat/fintoc-connect-page      → Task 16
  Agent E: git checkout -b feat/fintoc-status-settings   → Tasks 17, 18, 19, 20
  → Both merge to main when done

PHASE 4 (one agent):
  git checkout -b feat/fintoc-integration
  → Task 21
  → Merge to main → push to deploy
```
