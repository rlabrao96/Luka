# Luka — Plan 3: Household Logic

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement household privacy enforcement (Supabase RLS + partner aggregate RPC), contribution summary queries, Fintoc Open Banking reconciliation engine, joint account budget tracking API, and Supabase Vault integration for sensitive fields.

**Architecture:** Privacy enforced at two layers — Supabase RLS for row-level access control, and a SECURITY DEFINER PostgreSQL function that returns only aggregates for partner stats. Fintoc reconciliation runs as a nightly ARQ job using exact amount + date window + rapidfuzz fuzzy merchant matching. Supabase Vault stores OAuth tokens and phone numbers.

**Tech Stack:** SQLAlchemy async, Supabase RLS (SQL migrations), Fintoc Python SDK, rapidfuzz, ARQ, Supabase Vault (pgsodium)

**Spec:** `docs/superpowers/specs/2026-03-10-finanzas-personales-design.md` (Sections 3 RLS, 4 Modules 5-6)

**Prerequisite:** Plans 1 and 2 complete.

---

## Chunk 1: Supabase RLS Policies & Partner Stats

### File Map

```
backend/
├── alembic/versions/
│   ├── 002_rls_policies.py          ← enable RLS + policies on transactions
│   └── 003_partner_stats_rpc.py     ← SECURITY DEFINER aggregate function
├── modules/
│   └── households/
│       ├── router.py    ← updated with /summary, /partner-stats
│       └── service.py   ← updated with contribution_summary()
└── tests/
    └── test_household_privacy.py
```

---

### Task 1: RLS Migration

**Files:**
- Create: `backend/alembic/versions/002_rls_policies.py`

- [ ] **Step 1: Write failing privacy test**

Create `backend/tests/test_household_privacy.py`:
```python
import pytest
from modules.households.service import get_contribution_summary, get_partner_stats


@pytest.mark.asyncio
async def test_contribution_summary_returns_both_users(db, mock_user, mock_partner, mock_household):
    summary = await get_contribution_summary(db, household_id=mock_household.id)
    assert len(summary) == 2
    user_ids = {row["user_id"] for row in summary}
    assert mock_user.id in user_ids
    assert mock_partner.id in user_ids


@pytest.mark.asyncio
async def test_partner_stats_returns_only_aggregates(db, mock_user, mock_partner, mock_household):
    stats = await get_partner_stats(db, household_id=mock_household.id, requester_id=mock_user.id)
    assert "total_spent" in stats
    assert "by_category" in stats
    # Must NOT contain individual transaction rows
    assert "transactions" not in stats
```

Add `mock_household` fixture to `conftest.py`:
```python
@pytest.fixture
async def mock_household(db, mock_user, mock_partner) -> "Household":
    from modules.households.service import create_household
    from modules.households.models import HouseholdMember
    h = await create_household(db, mock_user, "Test Hogar", "couple")
    db.add(HouseholdMember(household_id=h.id, user_id=mock_partner.id, role="member"))
    await db.commit()
    return h
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_household_privacy.py -v
```

Expected: `FAILED — ImportError`

- [ ] **Step 3: Create RLS migration**

Create `backend/alembic/versions/002_rls_policies.py`:
```python
"""Enable RLS policies on transactions table.

Revision ID: 002
Down revision: 001 (your initial migration revision id)
"""
from alembic import op

revision = "002"
down_revision = "001"  # replace with actual revision id from 001


def upgrade():
    # Enable RLS on transactions
    op.execute("ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;")

    # Policy: users see their own transactions
    op.execute("""
        CREATE POLICY own_transactions ON transactions
        FOR SELECT
        USING (user_id = auth.uid());
    """)

    # Policy: all household members see shared transactions
    op.execute("""
        CREATE POLICY shared_transactions ON transactions
        FOR SELECT
        USING (
            household_id IN (
                SELECT household_id FROM household_members
                WHERE user_id = auth.uid()
            )
            AND id IN (
                SELECT transaction_id FROM transaction_splits
                WHERE split_type = 'shared'
            )
        );
    """)

    # Service role bypass for ARQ worker writes (no policy needed — service role bypasses RLS)

    # Partner aggregate stats function — SECURITY DEFINER so it can read all rows
    # but returns only aggregates, never raw partner rows
    op.execute("""
        CREATE OR REPLACE FUNCTION get_partner_stats(
            p_household_id UUID,
            p_viewer_id UUID,
            p_month DATE DEFAULT DATE_TRUNC('month', CURRENT_DATE)::DATE
        )
        RETURNS JSON
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        DECLARE
            partner_id UUID;
            result JSON;
        BEGIN
            -- Find partner (other member of household)
            SELECT user_id INTO partner_id
            FROM household_members
            WHERE household_id = p_household_id
              AND user_id != p_viewer_id
            LIMIT 1;

            IF partner_id IS NULL THEN
                RETURN '{"error": "no partner found"}'::JSON;
            END IF;

            SELECT json_build_object(
                'total_spent', COALESCE(SUM(t.amount), 0),
                'by_category', (
                    SELECT json_agg(json_build_object('category', ts.category, 'amount', SUM(t2.amount)))
                    FROM transactions t2
                    JOIN transaction_splits ts ON ts.transaction_id = t2.id
                    WHERE t2.user_id = partner_id
                      AND DATE_TRUNC('month', t2.transaction_date) = p_month::TIMESTAMPTZ
                      AND ts.category IS NOT NULL
                    GROUP BY ts.category
                    ORDER BY SUM(t2.amount) DESC
                    LIMIT 5
                )
            ) INTO result
            FROM transactions t
            WHERE t.user_id = partner_id
              AND DATE_TRUNC('month', t.transaction_date) = p_month::TIMESTAMPTZ;

            RETURN result;
        END;
        $$;
    """)


def downgrade():
    op.execute("DROP FUNCTION IF EXISTS get_partner_stats;")
    op.execute("DROP POLICY IF EXISTS shared_transactions ON transactions;")
    op.execute("DROP POLICY IF EXISTS own_transactions ON transactions;")
    op.execute("ALTER TABLE transactions DISABLE ROW LEVEL SECURITY;")
```

- [ ] **Step 4: Run migration**

```bash
alembic upgrade head
```

Expected: Migration applied. Check Supabase dashboard — transactions table should show RLS enabled.

- [ ] **Step 5: Implement contribution_summary and get_partner_stats in service.py**

Add to `backend/modules/households/service.py`:
```python
from sqlalchemy import text
import uuid


async def get_contribution_summary(db: AsyncSession, household_id: uuid.UUID) -> list[dict]:
    """Monthly household spending by member. No privacy restriction — both members see this."""
    result = await db.execute(
        text("""
        SELECT
            t.user_id,
            u.full_name,
            COALESCE(SUM(t.amount), 0) AS total_paid,
            COALESCE(SUM(t.amount) FILTER (WHERE ts.split_type = 'shared'), 0) AS shared_paid,
            COALESCE(SUM(t.amount) FILTER (WHERE ts.split_type = 'personal'), 0) AS personal_paid
        FROM transactions t
        JOIN transaction_splits ts ON ts.transaction_id = t.id
        JOIN users u ON u.id = t.user_id
        WHERE t.household_id = :household_id
          AND DATE_TRUNC('month', t.transaction_date) = DATE_TRUNC('month', NOW())
        GROUP BY t.user_id, u.full_name
        """),
        {"household_id": str(household_id)},
    )
    return [dict(row._mapping) for row in result.all()]


async def get_partner_stats(
    db: AsyncSession, household_id: uuid.UUID, requester_id: uuid.UUID
) -> dict:
    """Aggregate stats for partner only — no individual transaction rows."""
    result = await db.execute(
        text("SELECT get_partner_stats(:household_id, :viewer_id)"),
        {"household_id": str(household_id), "viewer_id": str(requester_id)},
    )
    return result.scalar()
```

- [ ] **Step 6: Add endpoints to households/router.py**

Add to `backend/modules/households/router.py`:
```python
@router.get("/{household_id}/summary")
async def household_summary(
    household_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_contribution_summary(db, uuid.UUID(household_id))


@router.get("/{household_id}/partner-stats")
async def partner_stats(
    household_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_partner_stats(db, uuid.UUID(household_id), current_user.id)
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/test_household_privacy.py tests/test_households.py -v
```

Expected: All tests `PASSED`.

- [ ] **Step 8: Commit**

```bash
git add backend/alembic/versions/002_rls_policies.py backend/modules/households/
git commit -m "feat: add Supabase RLS policies and partner aggregate stats RPC function"
```

---

## Chunk 2: Fintoc Reconciliation Engine

### File Map

```
backend/
├── modules/
│   └── fintoc/
│       ├── __init__.py
│       ├── client.py       ← Fintoc API wrapper (fetch settled transactions)
│       └── reconciler.py   ← match Fintoc transactions vs pending
├── jobs/tasks.py           ← updated: run_fintoc_sync job added
└── tests/
    └── test_fintoc_reconciler.py
```

---

### Task 2: Fintoc Client

**Files:**
- Create: `backend/modules/fintoc/__init__.py`
- Create: `backend/modules/fintoc/client.py`

- [ ] **Step 1: Create fintoc client**

Create `backend/modules/fintoc/__init__.py` (empty).

Create `backend/modules/fintoc/client.py`:
```python
from dataclasses import dataclass
from datetime import datetime, date
import httpx
from core.config import settings

FINTOC_BASE = "https://api.fintoc.com/v1"


@dataclass
class FintocTransaction:
    id: str
    amount: int
    description: str
    transaction_date: datetime
    account_id: str


class FintocClient:
    def __init__(self, link_token: str):
        self._link_token = link_token

    def _headers(self) -> dict:
        return {
            "Authorization": settings.fintoc_api_key,
            "X-Link-Token": self._link_token,
        }

    async def fetch_transactions(
        self, account_id: str, since: date, until: date
    ) -> list[FintocTransaction]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{FINTOC_BASE}/accounts/{account_id}/transactions",
                headers=self._headers(),
                params={"since": since.isoformat(), "until": until.isoformat()},
            )
            resp.raise_for_status()
            data = resp.json()

        return [
            FintocTransaction(
                id=txn["id"],
                amount=abs(int(txn["amount"])),
                description=(txn.get("description") or "").upper().strip(),
                transaction_date=datetime.fromisoformat(txn["post_date"]),
                account_id=account_id,
            )
            for txn in data
            if txn.get("type") == "charge"  # only debits
        ]
```

- [ ] **Step 2: Commit**

```bash
git add backend/modules/fintoc/
git commit -m "feat: add Fintoc client for fetching settled transactions"
```

---

### Task 3: Reconciliation Engine

**Files:**
- Create: `backend/modules/fintoc/reconciler.py`
- Create: `backend/tests/test_fintoc_reconciler.py`

- [ ] **Step 1: Write failing reconciler tests**

Create `backend/tests/test_fintoc_reconciler.py`:
```python
import pytest
from datetime import datetime
from modules.fintoc.reconciler import find_match, ReconcileResult
from modules.fintoc.client import FintocTransaction


def make_fintoc_txn(amount, description, days_offset=0):
    from datetime import timedelta
    return FintocTransaction(
        id=f"ftc_{amount}",
        amount=amount,
        description=description,
        transaction_date=datetime(2026, 3, 10) + timedelta(days=days_offset),
        account_id="acc-1",
    )


def test_exact_match_on_amount_and_merchant():
    pending = [
        {"id": "txn-1", "amount": 15990, "raw_merchant_name": "LIDER PROVI", "transaction_date": datetime(2026, 3, 10)},
    ]
    ftc = make_fintoc_txn(15990, "COMPRA LIDER PROVIDENCIA")
    result = find_match(ftc, pending)
    assert result is not None
    assert result.transaction_id == "txn-1"
    assert result.confidence >= 0.7


def test_no_match_on_wrong_amount():
    pending = [
        {"id": "txn-1", "amount": 20000, "raw_merchant_name": "LIDER PROVI", "transaction_date": datetime(2026, 3, 10)},
    ]
    ftc = make_fintoc_txn(15990, "LIDER")
    result = find_match(ftc, pending)
    assert result is None


def test_match_within_3_day_window():
    from datetime import timedelta
    pending = [
        {"id": "txn-1", "amount": 32000, "raw_merchant_name": "COPEC", "transaction_date": datetime(2026, 3, 8)},
    ]
    ftc = make_fintoc_txn(32000, "COPEC LAS CONDES", days_offset=2)  # 2 days later
    result = find_match(ftc, pending)
    assert result is not None


def test_no_match_outside_3_day_window():
    from datetime import timedelta
    pending = [
        {"id": "txn-1", "amount": 32000, "raw_merchant_name": "COPEC", "transaction_date": datetime(2026, 3, 1)},
    ]
    ftc = make_fintoc_txn(32000, "COPEC", days_offset=9)  # 9 days later
    result = find_match(ftc, pending)
    assert result is None
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_fintoc_reconciler.py -v
```

Expected: `FAILED — ImportError`

- [ ] **Step 3: Implement reconciler.py**

Create `backend/modules/fintoc/reconciler.py`:
```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from rapidfuzz import fuzz
from modules.fintoc.client import FintocTransaction
from modules.merchants.normalizer import normalize_merchant

_DATE_WINDOW_DAYS = 3
_FUZZY_THRESHOLD = 70.0


@dataclass
class ReconcileResult:
    transaction_id: str
    fintoc_id: str
    confidence: float


def find_match(
    fintoc_txn: FintocTransaction,
    pending_transactions: list[dict],
) -> ReconcileResult | None:
    """
    Attempt to match a settled Fintoc transaction against pending DB transactions.
    Matching criteria:
      - Exact amount match
      - Date within ±3 days
      - Fuzzy merchant name similarity > 70
    """
    fintoc_normalized = normalize_merchant(fintoc_txn.description)

    for pending in pending_transactions:
        # 1. Amount must match exactly
        if int(pending["amount"]) != fintoc_txn.amount:
            continue

        # 2. Date within ±3 days
        pending_date = pending["transaction_date"]
        if isinstance(pending_date, str):
            pending_date = datetime.fromisoformat(pending_date)

        delta = abs((fintoc_txn.transaction_date - pending_date).days)
        if delta > _DATE_WINDOW_DAYS:
            continue

        # 3. Fuzzy merchant similarity
        pending_normalized = normalize_merchant(pending["raw_merchant_name"])
        score = fuzz.partial_ratio(fintoc_normalized, pending_normalized)
        if score >= _FUZZY_THRESHOLD:
            return ReconcileResult(
                transaction_id=str(pending["id"]),
                fintoc_id=fintoc_txn.id,
                confidence=score / 100.0,
            )

    return None


async def reconcile_transactions(
    fintoc_transactions: list[FintocTransaction],
    db,
) -> dict:
    """
    Run reconciliation for a list of Fintoc settled transactions.
    Returns counts of matched and unmatched.
    """
    from sqlalchemy import select, update
    from modules.transactions.models import Transaction

    result = await db.execute(
        select(Transaction).where(Transaction.status == "pending")
    )
    pending = [
        {
            "id": str(t.id),
            "amount": int(t.amount),
            "raw_merchant_name": t.raw_merchant_name,
            "transaction_date": t.transaction_date,
        }
        for t in result.scalars().all()
    ]

    matched = 0
    unmatched = 0

    for ftc_txn in fintoc_transactions:
        match = find_match(ftc_txn, pending)
        if match:
            await db.execute(
                update(Transaction)
                .where(Transaction.id == match.transaction_id)
                .values(status="reconciled", fintoc_id=ftc_txn.id)
            )
            matched += 1
        else:
            # Insert as new settled transaction from Fintoc
            new_txn = Transaction(
                user_id=None,  # enriched from account owner in production
                household_id=None,
                raw_merchant_name=ftc_txn.description,
                amount=ftc_txn.amount,
                transaction_date=ftc_txn.transaction_date,
                source="fintoc",
                status="settled",
                fintoc_id=ftc_txn.id,
            )
            db.add(new_txn)
            unmatched += 1

    await db.commit()
    return {"matched": matched, "unmatched": unmatched}
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_fintoc_reconciler.py -v
```

Expected: All 4 tests `PASSED`.

- [ ] **Step 5: Add Fintoc sync job to tasks.py**

Add to `backend/jobs/tasks.py`:
```python
async def run_fintoc_sync(ctx: dict) -> None:
    """Nightly job: fetch settled Fintoc transactions and reconcile with pending."""
    from datetime import date, timedelta
    from modules.fintoc.client import FintocClient
    from modules.fintoc.reconciler import reconcile_transactions
    from modules.households.models import BankAccount
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(BankAccount).where(BankAccount.is_active == True)
        )
        accounts = result.scalars().all()

        for account in accounts:
            if not account.fintoc_link_id:
                continue
            try:
                client = FintocClient(link_token=account.fintoc_link_id)
                transactions = await client.fetch_transactions(
                    account_id=str(account.id),
                    since=date.today() - timedelta(days=7),
                    until=date.today(),
                )
                await reconcile_transactions(transactions, db)
            except Exception as e:
                await _record_failed_job(
                    "run_fintoc_sync", {"account_id": str(account.id)}, str(e), db
                )
```

Register in `worker.py`:
```python
from jobs.tasks import run_fintoc_sync

# In WorkerSettings:
cron_jobs = [
    cron(renew_mail_watches, hour=3, minute=0),
    cron(purge_raw_emails, minute=0),
    cron(cleanup_processed_webhooks, hour=4, minute=0),
    cron(run_fintoc_sync, hour=2, minute=0),   # 2am nightly
]
```

- [ ] **Step 6: Commit**

```bash
git add backend/modules/fintoc/ backend/jobs/tasks.py backend/worker.py \
        backend/tests/test_fintoc_reconciler.py
git commit -m "feat: add Fintoc reconciliation engine with fuzzy merchant matching"
```

---

## Chunk 3: Transactions API & Budget Tracking

### File Map

```
backend/
├── modules/
│   ├── transactions/
│   │   ├── router.py     ← GET /transactions/mine, /transactions/shared
│   │   ├── service.py    ← my_transactions(), shared_transactions()
│   │   └── schemas.py    ← TransactionResponse
│   └── budgets/
│       ├── __init__.py
│       ├── router.py     ← GET /budgets/monthly, POST /budgets/monthly
│       ├── service.py    ← monthly_budget_status()
│       └── schemas.py    ← BudgetStatusResponse
└── tests/
    ├── test_transactions_api.py
    └── test_budgets_api.py
```

---

### Task 4: Transactions API

**Files:**
- Create: `backend/modules/transactions/schemas.py`
- Create: `backend/modules/transactions/service.py`
- Create: `backend/modules/transactions/router.py`
- Create: `backend/tests/test_transactions_api.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_transactions_api.py`:
```python
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch


@pytest.mark.asyncio
async def test_my_transactions_requires_auth(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.get("/transactions/mine")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_my_transactions_returns_list(app, mock_user):
    with patch("modules.transactions.router.get_current_user", return_value=mock_user), \
         patch("modules.transactions.service.get_my_transactions", return_value=[]):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            response = await c.get("/transactions/mine", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_transactions_api.py -v
```

Expected: `FAILED — 404 Not Found`

- [ ] **Step 3: Implement transactions service and router**

Create `backend/modules/transactions/schemas.py`:
```python
import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class TransactionResponse(BaseModel):
    id: uuid.UUID
    raw_merchant_name: str
    amount: Decimal
    currency: str
    transaction_date: datetime
    category: str | None
    source: str
    status: str
    split_type: str | None = None

    model_config = {"from_attributes": True}
```

Create `backend/modules/transactions/service.py`:
```python
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from modules.transactions.models import Transaction, TransactionSplit


async def get_my_transactions(
    db: AsyncSession, user_id: uuid.UUID, limit: int = 50
) -> list[dict]:
    result = await db.execute(
        select(Transaction, TransactionSplit)
        .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.transaction_date.desc())
        .limit(limit)
    )
    rows = result.all()
    return [
        {**vars(txn), "split_type": split.split_type if split else None}
        for txn, split in rows
    ]


async def get_shared_transactions(
    db: AsyncSession, household_id: uuid.UUID, limit: int = 50
) -> list[dict]:
    result = await db.execute(
        select(Transaction, TransactionSplit)
        .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .where(
            Transaction.household_id == household_id,
            TransactionSplit.split_type == "shared",
        )
        .order_by(Transaction.transaction_date.desc())
        .limit(limit)
    )
    rows = result.all()
    return [
        {**vars(txn), "split_type": split.split_type}
        for txn, split in rows
    ]
```

Create `backend/modules/transactions/router.py`:
```python
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.transactions import service

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("/mine")
async def my_transactions(
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_my_transactions(db, current_user.id, limit=limit)


@router.get("/shared")
async def shared_transactions(
    household_id: uuid.UUID,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_shared_transactions(db, household_id, limit=limit)
```

Register in `main.py`:
```python
from modules.transactions.router import router as transactions_router
app.include_router(transactions_router)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_transactions_api.py -v
```

Expected: Both tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/transactions/ backend/tests/test_transactions_api.py
git commit -m "feat: add transactions API endpoints for personal and shared transactions"
```

---

### Task 5: Budget Tracking API (Joint Accounts)

**Files:**
- Create: `backend/modules/budgets/__init__.py`
- Create: `backend/modules/budgets/service.py`
- Create: `backend/modules/budgets/router.py`
- Create: `backend/modules/budgets/schemas.py`
- Create: `backend/tests/test_budgets_api.py`

- [ ] **Step 1: Write failing budget tests**

Create `backend/tests/test_budgets_api.py`:
```python
import pytest
from modules.budgets.service import get_budget_status


@pytest.mark.asyncio
async def test_budget_status_shows_remaining(db, mock_household):
    from modules.households.models import BankAccount, HouseholdBudget
    from datetime import date

    account = BankAccount(
        household_id=mock_household.id,
        user_id=None,  # filled in real flow
        bank_name="bci",
        account_type="joint",
    )
    db.add(account)
    await db.flush()

    budget = HouseholdBudget(
        household_id=mock_household.id,
        bank_account_id=account.id,
        month=date(2026, 3, 1),
        budgeted=500000,
    )
    db.add(budget)
    await db.commit()

    status = await get_budget_status(db, household_id=mock_household.id, month=date(2026, 3, 1))
    assert status["budgeted"] == 500000
    assert status["spent"] == 0
    assert status["available"] == 500000
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_budgets_api.py -v
```

Expected: `FAILED — ImportError`

- [ ] **Step 3: Implement budget service and router**

Create `backend/modules/budgets/__init__.py` (empty).

Create `backend/modules/budgets/service.py`:
```python
import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from modules.households.models import HouseholdBudget, BankAccount
from modules.transactions.models import Transaction, TransactionSplit


async def get_budget_status(
    db: AsyncSession,
    household_id: uuid.UUID,
    month: date,
) -> dict:
    # Sum all budgets for joint accounts this month
    budget_result = await db.execute(
        select(func.sum(HouseholdBudget.budgeted))
        .join(BankAccount, BankAccount.id == HouseholdBudget.bank_account_id)
        .where(
            HouseholdBudget.household_id == household_id,
            HouseholdBudget.month == month,
            BankAccount.account_type == "joint",
        )
    )
    total_budgeted = float(budget_result.scalar() or 0)

    # Sum all shared spending this month
    spent_result = await db.execute(
        select(func.sum(Transaction.amount))
        .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .where(
            Transaction.household_id == household_id,
            TransactionSplit.split_type == "shared",
            func.date_trunc("month", Transaction.transaction_date) == func.date_trunc("month", func.cast(month, type_=Transaction.transaction_date.type)),
        )
    )
    total_spent = float(spent_result.scalar() or 0)

    return {
        "household_id": str(household_id),
        "month": month.isoformat(),
        "budgeted": total_budgeted,
        "spent": total_spent,
        "available": total_budgeted - total_spent,
        "percent_used": round((total_spent / total_budgeted * 100) if total_budgeted > 0 else 0, 1),
    }


async def set_monthly_budget(
    db: AsyncSession,
    household_id: uuid.UUID,
    bank_account_id: uuid.UUID,
    month: date,
    amount: float,
) -> HouseholdBudget:
    # Upsert: update if exists, insert if not
    result = await db.execute(
        select(HouseholdBudget).where(
            HouseholdBudget.household_id == household_id,
            HouseholdBudget.bank_account_id == bank_account_id,
            HouseholdBudget.month == month,
        )
    )
    budget = result.scalar_one_or_none()
    if budget:
        budget.budgeted = amount
    else:
        budget = HouseholdBudget(
            household_id=household_id,
            bank_account_id=bank_account_id,
            month=month,
            budgeted=amount,
        )
        db.add(budget)
    await db.commit()
    await db.refresh(budget)
    return budget
```

Create `backend/modules/budgets/schemas.py`:
```python
import uuid
from datetime import date
from pydantic import BaseModel


class BudgetStatusResponse(BaseModel):
    household_id: str
    month: str
    budgeted: float
    spent: float
    available: float
    percent_used: float


class SetBudgetRequest(BaseModel):
    bank_account_id: uuid.UUID
    month: date
    amount: float
```

Create `backend/modules/budgets/router.py`:
```python
import uuid
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.budgets import service
from modules.budgets.schemas import BudgetStatusResponse, SetBudgetRequest

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("/monthly/{household_id}", response_model=BudgetStatusResponse)
async def monthly_budget(
    household_id: uuid.UUID,
    month: date = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not month:
        from datetime import date as d
        today = d.today()
        month = d(today.year, today.month, 1)
    return await service.get_budget_status(db, household_id, month)


@router.post("/monthly/{household_id}")
async def set_budget(
    household_id: uuid.UUID,
    body: SetBudgetRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.set_monthly_budget(
        db, household_id, body.bank_account_id, body.month, body.amount
    )
```

Register in `main.py`:
```python
from modules.budgets.router import router as budgets_router
app.include_router(budgets_router)
```

- [ ] **Step 4: Run all tests**

```bash
pytest tests/ -v --tb=short
```

Expected: All tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/budgets/ backend/tests/test_budgets_api.py
git commit -m "feat: add joint account budget tracking API with monthly status and upsert"
```

---

## Plan 3 Complete ✅

**What you now have:**
- Supabase RLS policies enforced on transactions table
- `get_partner_stats` SECURITY DEFINER function — returns only aggregates, never raw rows
- Household contribution summary query (monthly totals by member)
- Fintoc client + reconciliation engine (exact amount + ±3 day window + rapidfuzz ≥70)
- Nightly ARQ job for Fintoc sync
- Transactions API: `/transactions/mine` and `/transactions/shared`
- Budget tracking API: monthly status + set budget for joint accounts

**Next:** [Plan 4 — Frontend Dashboard](./2026-03-10-luka-plan-4-frontend-dashboard.md)
(Next.js dashboard pages, charts, responsive layout, API integration)
