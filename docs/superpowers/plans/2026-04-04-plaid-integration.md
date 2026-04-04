# Plaid Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Plaid as a bank connection provider for US users, with a country selector UX, daily transaction sync, and shared reconciliation system for both providers.

**Architecture:** Separate `modules/plaid/` module alongside existing `modules/bank_connect/`. Plaid uses OAuth tokens + cursor-based sync (no credential storage). A shared reconciliation utility handles dedup, fuzzy matching, and transfer detection for both providers.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, plaid-python, ARQ workers, Next.js 14, react-plaid-link, Tailwind CSS

**Spec:** `docs/superpowers/specs/2026-04-04-plaid-integration-design.md`

---

## Parallel Execution Map

```
Task 1 (Migration) ──────────────────────────┐
                                              ├── must complete before Tasks 2-5
Task 2 (Backend Models + Service) ───────┐    │
Task 3 (Reconciliation Utility)  ────────┤    │
Task 4 (Frontend)                ────────┘    │
                                              │
Task 2 ──► Task 5 (Sync + Router + Worker)    │
Task 3 ──► Task 5                             │
Task 4 is independent (API contract defined)  │
                                              │
Task 5 (Integration) ──► Task 6 (Config + Wiring)
```

**Parallel groups:**
- **Group A (sequential):** Task 1 alone
- **Group B (parallel after Task 1):** Tasks 2, 3, 4 — all independent
- **Group C (sequential after Group B):** Task 5 (depends on 2+3)
- **Group D (sequential after Task 5):** Task 6 (final wiring)

---

## Task 1: Database Migration

**Depends on:** nothing
**Blocks:** Tasks 2, 3, 4, 5

**Files:**
- Create: `backend/alembic/versions/023_plaid_integration.py`

- [ ] **Step 1: Create the migration file**

```bash
cd backend && alembic revision -m "plaid_integration" --rev-id 023
```

- [ ] **Step 2: Write migration with all schema changes**

Edit `backend/alembic/versions/023_plaid_integration.py`:

```python
"""plaid_integration

Revision ID: 023
Revises: 022
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create plaid_items table
    op.create_table(
        "plaid_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("household_id", UUID(as_uuid=True), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plaid_item_id", sa.String, nullable=False, unique=True),
        sa.Column("access_token", sa.String, nullable=False),
        sa.Column("institution_id", sa.String, nullable=False),
        sa.Column("institution_name", sa.String, nullable=False),
        sa.Column("cursor", sa.Text, nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_status", sa.String, nullable=True),
        sa.Column("error_code", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # 2. Add columns to bank_accounts
    op.add_column("bank_accounts", sa.Column("provider", sa.String, server_default="luka_connect", nullable=False))
    op.add_column("bank_accounts", sa.Column("country", sa.String(2), server_default="CL", nullable=False))
    op.add_column("bank_accounts", sa.Column(
        "plaid_item_id", UUID(as_uuid=True),
        sa.ForeignKey("plaid_items.id", ondelete="SET NULL"), nullable=True,
    ))
    op.add_column("bank_accounts", sa.Column("plaid_account_id", sa.String, nullable=True))

    # 3. Add columns to transactions
    op.add_column("transactions", sa.Column("transfer_pair_id", UUID(as_uuid=True), nullable=True))
    op.add_column("transactions", sa.Column("plaid_transaction_id", sa.String, nullable=True))

    # 4. Partial unique index on plaid_transaction_id
    op.create_index(
        "ix_transactions_plaid_transaction_id",
        "transactions",
        ["plaid_transaction_id"],
        unique=True,
        postgresql_where=sa.text("plaid_transaction_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_plaid_transaction_id", table_name="transactions")
    op.drop_column("transactions", "plaid_transaction_id")
    op.drop_column("transactions", "transfer_pair_id")
    op.drop_column("bank_accounts", "plaid_account_id")
    op.drop_column("bank_accounts", "plaid_item_id")
    op.drop_column("bank_accounts", "country")
    op.drop_column("bank_accounts", "provider")
    op.drop_table("plaid_items")
```

- [ ] **Step 3: Run the migration**

```bash
cd backend && alembic upgrade head
```

Expected: Migration applies cleanly, no errors.

- [ ] **Step 4: Verify tables exist**

```bash
cd backend && python -c "
from sqlalchemy import inspect, create_engine
from core.config import settings
engine = create_engine(settings.database_url.replace('+asyncpg', ''))
insp = inspect(engine)
cols = [c['name'] for c in insp.get_columns('plaid_items')]
print('plaid_items columns:', cols)
ba_cols = [c['name'] for c in insp.get_columns('bank_accounts')]
print('bank_accounts has provider:', 'provider' in ba_cols)
print('bank_accounts has country:', 'country' in ba_cols)
tx_cols = [c['name'] for c in insp.get_columns('transactions')]
print('transactions has plaid_transaction_id:', 'plaid_transaction_id' in tx_cols)
print('transactions has transfer_pair_id:', 'transfer_pair_id' in tx_cols)
"
```

Expected: All columns present.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/023_plaid_integration.py
git commit -m "feat: add migration 023 for Plaid integration (plaid_items table, bank_accounts + transactions columns)"
```

---

## Task 2: Backend Plaid Models, Service, and Mapper

**Depends on:** Task 1
**Blocks:** Task 5
**Can run in parallel with:** Tasks 3, 4

**Files:**
- Create: `backend/modules/plaid/__init__.py`
- Create: `backend/modules/plaid/models.py`
- Create: `backend/modules/plaid/service.py`
- Create: `backend/modules/plaid/mapper.py`
- Modify: `backend/modules/households/models.py:43-65` (add new columns to BankAccount)
- Modify: `backend/modules/transactions/models.py:9-38` (add new columns to Transaction)
- Modify: `backend/core/config.py:4-49` (add Plaid env vars)
- Modify: `backend/pyproject.toml` (add plaid-python dependency)

- [ ] **Step 1: Install plaid-python dependency**

Edit `backend/pyproject.toml` — add `"plaid-python>=29.0.0"` to the `dependencies` list (after the existing dependencies around line 20).

Then install:

```bash
cd backend && pip install -e ".[dev]"
```

- [ ] **Step 2: Add Plaid env vars to config**

Edit `backend/core/config.py` — add these three lines after the existing env var declarations (around line 47, before the class ends):

```python
    plaid_client_id: str = ""
    plaid_secret: str = ""
    plaid_env: str = "sandbox"  # "sandbox" or "production"
```

- [ ] **Step 3: Add new columns to BankAccount model**

Edit `backend/modules/households/models.py` — add after `is_active` (line 64):

```python
    provider: Mapped[str] = mapped_column(String, default="luka_connect", server_default="luka_connect")
    country: Mapped[str] = mapped_column(String(2), default="CL", server_default="CL")
    plaid_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("plaid_items.id", ondelete="SET NULL"), nullable=True
    )
    plaid_account_id: Mapped[str | None] = mapped_column(String, nullable=True)
```

- [ ] **Step 4: Add new columns to Transaction model**

Edit `backend/modules/transactions/models.py` — add after `raw_email_text` (line 34):

```python
    transfer_pair_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    plaid_transaction_id: Mapped[str | None] = mapped_column(String, nullable=True, unique=False)
```

Note: The unique constraint is handled by the partial index in the migration, not the model.

- [ ] **Step 5: Create plaid module init**

Create `backend/modules/plaid/__init__.py` — empty file.

- [ ] **Step 6: Create PlaidItem model**

Create `backend/modules/plaid/models.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class PlaidItem(Base):
    __tablename__ = "plaid_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    plaid_item_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    access_token: Mapped[str] = mapped_column(String, nullable=False)
    institution_id: Mapped[str] = mapped_column(String, nullable=False)
    institution_name: Mapped[str] = mapped_column(String, nullable=False)
    cursor: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[str | None] = mapped_column(String, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 7: Create Plaid service (API client wrapper)**

Create `backend/modules/plaid/service.py`:

```python
import uuid

import plaid
from plaid.api import plaid_api
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.item_remove_request import ItemRemoveRequest

from core.config import settings


def _get_client() -> plaid_api.PlaidApi:
    env_map = {
        "sandbox": plaid.Environment.Sandbox,
        "production": plaid.Environment.Production,
    }
    configuration = plaid.Configuration(
        host=env_map.get(settings.plaid_env, plaid.Environment.Sandbox),
        api_key={
            "clientId": settings.plaid_client_id,
            "secret": settings.plaid_secret,
        },
    )
    api_client = plaid.ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)


def create_link_token(user_id: uuid.UUID) -> str:
    client = _get_client()
    request = LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id=str(user_id)),
        client_name="Luka",
        products=[Products("transactions")],
        country_codes=[CountryCode("US")],
        language="en",
    )
    response = client.link_token_create(request)
    return response.link_token


def exchange_public_token(public_token: str) -> tuple[str, str]:
    client = _get_client()
    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    response = client.item_public_token_exchange(request)
    return response.access_token, response.item_id


def sync_transactions(access_token: str, cursor: str | None, count: int = 500):
    client = _get_client()
    request = TransactionsSyncRequest(
        access_token=access_token,
        count=count,
    )
    if cursor:
        request.cursor = cursor
    response = client.transactions_sync(request)
    return response


def remove_item(access_token: str) -> None:
    client = _get_client()
    request = ItemRemoveRequest(access_token=access_token)
    client.item_remove(request)
```

- [ ] **Step 8: Create Plaid transaction mapper**

Create `backend/modules/plaid/mapper.py`:

```python
from datetime import datetime, timezone


ACCOUNT_KIND_MAP = {
    ("depository", "checking"): "checking_account",
    ("depository", "savings"): "savings_account",
    ("credit", "credit card"): "credit_card",
}


def map_account_kind(plaid_type: str, plaid_subtype: str | None) -> str:
    return ACCOUNT_KIND_MAP.get((plaid_type, plaid_subtype), "other")


def map_plaid_transaction(plaid_tx, bank_account_id: str, user_id: str, household_id: str) -> dict:
    """Map a Plaid transaction object to a Luka transaction dict.

    Sign convention: Plaid positive = outflow (expense), Luka negative = expense.
    So we multiply by -1.
    """
    plaid_amount = float(plaid_tx.amount)
    luka_amount = plaid_amount * -1

    # Derive transaction_type from Plaid's amount sign (before our flip)
    transaction_type = "expense" if plaid_amount > 0 else "income"

    # Use merchant_name if available, fall back to name
    raw_name = plaid_tx.merchant_name or plaid_tx.name or "Unknown"

    # Status from pending flag
    status = "pending" if plaid_tx.pending else "confirmed"

    return {
        "user_id": user_id,
        "household_id": household_id,
        "bank_account_id": bank_account_id,
        "raw_merchant_name": raw_name,
        "amount": luka_amount,
        "currency": plaid_tx.iso_currency_code or "USD",
        "transaction_date": datetime.combine(plaid_tx.date, datetime.min.time()).replace(tzinfo=timezone.utc),
        "source": "plaid",
        "source_type": "plaid",
        "status": status,
        "transaction_type": transaction_type,
        "plaid_transaction_id": plaid_tx.transaction_id,
    }


def is_plaid_transfer(plaid_tx) -> bool:
    """Check if Plaid's personal_finance_category indicates a transfer."""
    pfc = getattr(plaid_tx, "personal_finance_category", None)
    if not pfc:
        return False
    primary = getattr(pfc, "primary", "")
    return primary in ("TRANSFER_IN", "TRANSFER_OUT", "LOAN_PAYMENTS")
```

- [ ] **Step 9: Commit**

```bash
git add backend/modules/plaid/ backend/modules/households/models.py backend/modules/transactions/models.py backend/core/config.py backend/pyproject.toml
git commit -m "feat: add Plaid module foundations (models, service, mapper) and update existing models"
```

---

## Task 3: Shared Transaction Reconciliation Utility

**Depends on:** Task 1
**Blocks:** Task 5
**Can run in parallel with:** Tasks 2, 4

**Files:**
- Create: `backend/modules/reconciliation/__init__.py`
- Create: `backend/modules/reconciliation/dedup.py`
- Create: `backend/modules/reconciliation/transfers.py`

- [ ] **Step 1: Create reconciliation module init**

Create `backend/modules/reconciliation/__init__.py` — empty file.

- [ ] **Step 2: Create email dedup-and-enrich utility**

Create `backend/modules/reconciliation/dedup.py`:

```python
"""Shared email dedup-and-enrich logic for both Plaid and luka-connect sync.

When a bank sync transaction matches an email transaction:
1. Copy enrichment data (merchant_id, account_type, splits, custom merchant name)
2. Apply to the bank transaction
3. Delete the email transaction

Matching priority:
1. Exact: same merchant, ±2 days, exact amount
2. Fuzzy: same merchant, ±3 days, amount within 30%
3. Sum: same merchant, ±3 days, sum of N email txs within 5%
"""
import uuid
from datetime import timedelta

from sqlalchemy import and_, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from modules.transactions.models import Transaction, TransactionSplit


async def find_email_match(
    session: AsyncSession,
    user_id: uuid.UUID,
    raw_merchant_name: str,
    amount: float,
    tx_date,
    source_bank_name: str | None = None,
) -> dict | None:
    """Find matching email transaction(s) using 3-tier priority.

    Returns dict with:
      - match_type: "exact" | "fuzzy" | "sum"
      - email_tx_ids: list of matched email transaction IDs
      - enrichment: dict of fields to copy to bank tx
    Or None if no match found.
    """
    abs_amount = abs(amount)

    # --- Priority 1: Exact match ---
    exact_match = await _find_single_match(
        session, user_id, raw_merchant_name, amount, tx_date,
        day_window=2, amount_tolerance=0.0,
    )
    if exact_match:
        enrichment = await _extract_enrichment(session, exact_match.id)
        return {"match_type": "exact", "email_tx_ids": [exact_match.id], "enrichment": enrichment}

    # --- Priority 2: Fuzzy match (within 30%) ---
    fuzzy_match = await _find_single_match(
        session, user_id, raw_merchant_name, amount, tx_date,
        day_window=3, amount_tolerance=0.30,
    )
    if fuzzy_match:
        enrichment = await _extract_enrichment(session, fuzzy_match.id)
        return {"match_type": "fuzzy", "email_tx_ids": [fuzzy_match.id], "enrichment": enrichment}

    # --- Priority 3: Sum match (N email txs sum to bank amount, within 5%) ---
    sum_result = await _find_sum_match(
        session, user_id, raw_merchant_name, abs_amount, tx_date,
        day_window=3, sum_tolerance=0.05,
    )
    if sum_result:
        # Use enrichment from the largest email tx
        primary_tx_id = sum_result["primary_tx_id"]
        enrichment = await _extract_enrichment(session, primary_tx_id)
        return {"match_type": "sum", "email_tx_ids": sum_result["tx_ids"], "enrichment": enrichment}

    return None


async def apply_match_and_delete_emails(
    session: AsyncSession,
    bank_tx_id: uuid.UUID,
    email_tx_ids: list[uuid.UUID],
    enrichment: dict,
) -> None:
    """Apply enrichment from email tx to bank tx, re-link splits, delete email txs."""
    # Apply enrichment fields to bank transaction
    update_fields = {}
    if enrichment.get("merchant_id"):
        update_fields["merchant_id"] = enrichment["merchant_id"]
    if enrichment.get("category"):
        update_fields["category"] = enrichment["category"]
    if enrichment.get("transaction_type") and enrichment["transaction_type"] != "expense":
        update_fields["transaction_type"] = enrichment["transaction_type"]

    if update_fields:
        await session.execute(
            update(Transaction).where(Transaction.id == bank_tx_id).values(**update_fields)
        )

    # Re-link any transaction_splits from email txs to the bank tx
    for email_id in email_tx_ids:
        await session.execute(
            update(TransactionSplit)
            .where(TransactionSplit.transaction_id == email_id)
            .values(transaction_id=bank_tx_id)
        )

    # Delete email transactions
    await session.execute(
        delete(Transaction).where(Transaction.id.in_(email_tx_ids))
    )


async def _find_single_match(
    session: AsyncSession,
    user_id: uuid.UUID,
    raw_merchant_name: str,
    amount: float,
    tx_date,
    day_window: int,
    amount_tolerance: float,
) -> Transaction | None:
    """Find a single email transaction matching by merchant, date window, and amount tolerance."""
    date_min = tx_date - timedelta(days=day_window)
    date_max = tx_date + timedelta(days=day_window)

    conditions = [
        Transaction.user_id == user_id,
        Transaction.source_type == "email",
        Transaction.transaction_date >= date_min,
        Transaction.transaction_date <= date_max,
        Transaction.raw_merchant_name.ilike(f"%{raw_merchant_name[:10]}%") if raw_merchant_name else True,
    ]

    if amount_tolerance == 0.0:
        conditions.append(Transaction.amount == amount)
    else:
        abs_amount = abs(amount)
        lower = abs_amount * (1 - amount_tolerance)
        upper = abs_amount * (1 + amount_tolerance)
        from sqlalchemy import func as sa_func
        conditions.append(sa_func.abs(Transaction.amount) >= lower)
        conditions.append(sa_func.abs(Transaction.amount) <= upper)
        # Same sign
        if amount < 0:
            conditions.append(Transaction.amount < 0)
        else:
            conditions.append(Transaction.amount > 0)

    result = await session.execute(
        select(Transaction).where(and_(*conditions)).limit(1)
    )
    return result.scalar_one_or_none()


async def _find_sum_match(
    session: AsyncSession,
    user_id: uuid.UUID,
    raw_merchant_name: str,
    abs_amount: float,
    tx_date,
    day_window: int,
    sum_tolerance: float,
) -> dict | None:
    """Find N email transactions from same merchant whose sum matches the bank amount."""
    date_min = tx_date - timedelta(days=day_window)
    date_max = tx_date + timedelta(days=day_window)

    result = await session.execute(
        select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.source_type == "email",
            Transaction.transaction_date >= date_min,
            Transaction.transaction_date <= date_max,
        ).order_by(Transaction.amount.desc())
    )
    candidates = result.scalars().all()

    if len(candidates) < 2:
        return None

    total = sum(abs(c.amount) for c in candidates)
    lower = abs_amount * (1 - sum_tolerance)
    upper = abs_amount * (1 + sum_tolerance)

    if lower <= total <= upper:
        # Find the largest tx for enrichment source
        primary = max(candidates, key=lambda c: abs(c.amount))
        return {
            "tx_ids": [c.id for c in candidates],
            "primary_tx_id": primary.id,
        }

    return None


async def _extract_enrichment(session: AsyncSession, email_tx_id: uuid.UUID) -> dict:
    """Extract enrichment data from an email transaction."""
    result = await session.execute(
        select(Transaction).where(Transaction.id == email_tx_id)
    )
    tx = result.scalar_one_or_none()
    if not tx:
        return {}

    return {
        "merchant_id": tx.merchant_id,
        "category": tx.category,
        "transaction_type": tx.transaction_type,
        "account_type": getattr(tx, "account_type", None),  # personal/joint from splits
    }
```

- [ ] **Step 3: Create transfer detection utility**

Create `backend/modules/reconciliation/transfers.py`:

```python
"""Transfer detection: identifies inter-account transfers and CC payments.

Detection methods (in order):
1. Plaid category tags (TRANSFER_IN, TRANSFER_OUT, LOAN_PAYMENTS)
2. Cross-account amount matching (same amount, ±2 days, opposite signs, same household)

When detected, both transactions get transaction_type="transfer" and a shared transfer_pair_id.
"""
import uuid
from datetime import timedelta

from sqlalchemy import and_, func as sa_func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from modules.transactions.models import Transaction


async def detect_transfers(
    session: AsyncSession,
    household_id: uuid.UUID,
    lookback_days: int = 5,
) -> int:
    """Scan recent transactions for transfer pairs. Returns number of pairs detected."""
    from datetime import datetime, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    pairs_found = 0

    # Get all recent non-transfer transactions for this household
    result = await session.execute(
        select(Transaction).where(
            Transaction.household_id == household_id,
            Transaction.transaction_type != "transfer",
            Transaction.transaction_date >= cutoff,
            Transaction.transfer_pair_id.is_(None),
        ).order_by(Transaction.transaction_date)
    )
    transactions = result.scalars().all()

    # Build index by absolute amount for O(n) matching
    matched_ids: set[uuid.UUID] = set()

    for i, tx_a in enumerate(transactions):
        if tx_a.id in matched_ids:
            continue

        for tx_b in transactions[i + 1:]:
            if tx_b.id in matched_ids:
                continue

            # Must be different accounts
            if tx_a.bank_account_id == tx_b.bank_account_id:
                continue
            if tx_a.bank_account_id is None or tx_b.bank_account_id is None:
                continue

            # Same absolute amount, opposite signs
            if abs(abs(tx_a.amount) - abs(tx_b.amount)) > 0.01:
                continue
            if (tx_a.amount > 0) == (tx_b.amount > 0):
                continue

            # Within ±2 days
            day_diff = abs((tx_a.transaction_date - tx_b.transaction_date).days)
            if day_diff > 2:
                continue

            # Match found — mark both as transfers
            pair_id = uuid.uuid4()
            await session.execute(
                update(Transaction)
                .where(Transaction.id.in_([tx_a.id, tx_b.id]))
                .values(transaction_type="transfer", transfer_pair_id=pair_id)
            )
            matched_ids.add(tx_a.id)
            matched_ids.add(tx_b.id)
            pairs_found += 1
            break

    return pairs_found
```

- [ ] **Step 4: Commit**

```bash
git add backend/modules/reconciliation/
git commit -m "feat: add shared transaction reconciliation (dedup + transfer detection)"
```

---

## Task 4: Frontend — Country Selector, Plaid Link, and Bank Card Updates

**Depends on:** Task 1 (for API contract, not runtime)
**Can run in parallel with:** Tasks 2, 3

**Files:**
- Modify: `frontend/package.json` (add react-plaid-link)
- Modify: `frontend/app/lib/api.ts:437-450` (add Plaid API functions)
- Create: `frontend/app/(dashboard)/settings/components/CountrySelectorModal.tsx`
- Create: `frontend/app/(dashboard)/settings/components/PlaidLinkButton.tsx`
- Modify: `frontend/app/(dashboard)/settings/components/BankAccountsSection.tsx:622-660` (country selector + flags)

- [ ] **Step 1: Install react-plaid-link**

```bash
cd frontend && npm install react-plaid-link
```

- [ ] **Step 2: Add Plaid API functions to api.ts**

Edit `frontend/app/lib/api.ts` — add after the existing bank-connect functions (around line 451):

```typescript
// Plaid (US banks)
export async function createPlaidLinkToken(): Promise<{ link_token: string }> {
  const res = await api.post("/plaid/create-link-token");
  return res.data;
}

export async function exchangePlaidToken(
  publicToken: string,
  institutionId: string,
  institutionName: string
): Promise<{ plaid_item_id: string }> {
  const res = await api.post("/plaid/exchange-token", {
    public_token: publicToken,
    institution_id: institutionId,
    institution_name: institutionName,
  });
  return res.data;
}

export async function disconnectPlaid(plaidItemId: string): Promise<void> {
  await api.delete(`/plaid/disconnect?plaid_item_id=${plaidItemId}`);
}

export async function syncPlaid(plaidItemId: string): Promise<void> {
  await api.post(`/plaid/sync?plaid_item_id=${plaidItemId}`);
}
```

- [ ] **Step 3: Create CountrySelectorModal component**

Create `frontend/app/(dashboard)/settings/components/CountrySelectorModal.tsx`:

```tsx
"use client";

import { Dialog, DialogContent } from "@/components/ui/dialog";

interface CountrySelectorModalProps {
  open: boolean;
  onClose: () => void;
  onSelectChile: () => void;
  onSelectUSA: () => void;
}

export function CountrySelectorModal({
  open,
  onClose,
  onSelectChile,
  onSelectUSA,
}: CountrySelectorModalProps) {
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-[320px]">
        <div className="flex flex-col items-center gap-6 py-4">
          <p className="text-sm text-muted-foreground">
            Selecciona el pais de la cuenta
          </p>
          <div className="flex gap-8">
            <button
              onClick={onSelectChile}
              className="flex flex-col items-center gap-2 p-4 rounded-xl border-2 border-transparent hover:border-luka-primary hover:bg-luka-light transition-all"
            >
              <span className="text-5xl">🇨🇱</span>
            </button>
            <button
              onClick={onSelectUSA}
              className="flex flex-col items-center gap-2 p-4 rounded-xl border-2 border-transparent hover:border-luka-primary hover:bg-luka-light transition-all"
            >
              <span className="text-5xl">🇺🇸</span>
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 4: Create PlaidLinkButton component**

Create `frontend/app/(dashboard)/settings/components/PlaidLinkButton.tsx`:

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import { usePlaidLink } from "react-plaid-link";
import { createPlaidLinkToken, exchangePlaidToken } from "@/app/lib/api";
import { useQueryClient } from "@tanstack/react-query";

interface PlaidLinkButtonProps {
  onComplete: () => void;
  onError?: (error: string) => void;
}

export function usePlaidConnection({ onComplete, onError }: PlaidLinkButtonProps) {
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const queryClient = useQueryClient();

  const startPlaidLink = useCallback(async () => {
    setLoading(true);
    try {
      const { link_token } = await createPlaidLinkToken();
      setLinkToken(link_token);
    } catch (e) {
      onError?.("Error al conectar con Plaid");
      setLoading(false);
    }
  }, [onError]);

  const onSuccess = useCallback(
    async (publicToken: string, metadata: any) => {
      try {
        await exchangePlaidToken(
          publicToken,
          metadata.institution.institution_id,
          metadata.institution.name
        );
        queryClient.invalidateQueries({ queryKey: ["bank-accounts"] });
        queryClient.invalidateQueries({ queryKey: ["bank-connections"] });
        onComplete();
      } catch (e) {
        onError?.("Error al vincular cuenta");
      } finally {
        setLinkToken(null);
        setLoading(false);
      }
    },
    [onComplete, onError, queryClient]
  );

  const onExit = useCallback(() => {
    setLinkToken(null);
    setLoading(false);
  }, []);

  const { open, ready } = usePlaidLink({
    token: linkToken,
    onSuccess,
    onExit,
  });

  useEffect(() => {
    if (linkToken && ready) {
      open();
    }
  }, [linkToken, ready, open]);

  return { startPlaidLink, loading };
}
```

- [ ] **Step 5: Update BankAccountsSection with country selector and flags**

Edit `frontend/app/(dashboard)/settings/components/BankAccountsSection.tsx`:

1. Add imports at the top:

```tsx
import { CountrySelectorModal } from "./CountrySelectorModal";
import { usePlaidConnection } from "./PlaidLinkButton";
import { disconnectPlaid, syncPlaid } from "@/app/lib/api";
```

2. Inside the component, add state and handler (near the existing `showModal` state):

```tsx
const [showCountrySelector, setShowCountrySelector] = useState(false);

const { startPlaidLink, loading: plaidLoading } = usePlaidConnection({
  onComplete: () => setShowCountrySelector(false),
});
```

3. Change the "+ Conectar banco" button's `onClick` from `() => setShowModal(true)` to `() => setShowCountrySelector(true)`.

4. Add the CountrySelectorModal right before the closing `</div>` of the section:

```tsx
<CountrySelectorModal
  open={showCountrySelector}
  onClose={() => setShowCountrySelector(false)}
  onSelectChile={() => {
    setShowCountrySelector(false);
    setShowModal(true); // opens existing luka-connect modal
  }}
  onSelectUSA={() => {
    setShowCountrySelector(false);
    startPlaidLink();
  }}
/>
```

5. Add flag icons to bank connection cards. In the card rendering where `bank_name` is displayed, prepend the flag:

```tsx
<span className="mr-1.5">{connection.country === "US" ? "🇺🇸" : "🇨🇱"}</span>
```

6. For detected accounts grouped by bank, add the same flag before the bank name header.

7. For Plaid banks with `error_code = "ITEM_LOGIN_REQUIRED"`, show a warning badge and a "Reconectar" button instead of "Sincronizar ahora". The reconnect button should call `createPlaidLinkToken()` and open Plaid Link — Plaid automatically handles update mode when the Item already exists.

- [ ] **Step 6: Commit**

```bash
cd frontend && git add package.json package-lock.json app/lib/api.ts app/\(dashboard\)/settings/components/
git commit -m "feat: add frontend country selector, Plaid Link integration, and flag badges"
```

---

## Task 5: Plaid Sync Logic, Router, and Worker Integration

**Depends on:** Tasks 2, 3
**Blocks:** Task 6

**Files:**
- Create: `backend/modules/plaid/sync.py`
- Create: `backend/modules/plaid/router.py`
- Modify: `backend/jobs/tasks.py` (add Plaid task functions at end of file)
- Modify: `backend/jobs/queue.py:6` (update `enqueue_job` to accept `*args` and `**kwargs`)
- Modify: `backend/worker.py:5-33` (import new functions, add to functions list and cron jobs)

- [ ] **Step 1: Create Plaid sync logic**

Create `backend/modules/plaid/sync.py`:

```python
"""Plaid transaction sync: fetches transactions via cursor, creates accounts, maps and deduplicates."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from modules.plaid.models import PlaidItem
from modules.plaid.mapper import map_plaid_transaction, map_account_kind, is_plaid_transfer
from modules.plaid.service import sync_transactions
from modules.households.models import BankAccount
from modules.transactions.models import Transaction
from modules.reconciliation.dedup import find_email_match, apply_match_and_delete_emails


async def run_plaid_sync(session: AsyncSession, plaid_item_id: uuid.UUID, initial: bool = False) -> dict:
    """Run a full sync for a Plaid item. Returns stats dict."""
    result = await session.execute(
        select(PlaidItem).where(PlaidItem.id == plaid_item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        return {"error": "PlaidItem not found"}

    if item.error_code:
        return {"error": f"Item has error: {item.error_code}"}

    cursor = item.cursor
    all_added = []
    all_modified = []
    all_removed = []
    accounts_data = []

    try:
        # Paginate through all updates
        has_more = True
        while has_more:
            kwargs = {"access_token": item.access_token, "cursor": cursor}
            if initial and not cursor:
                kwargs["count"] = 500
            response = sync_transactions(**kwargs)

            all_added.extend(response.added)
            all_modified.extend(response.modified)
            all_removed.extend(response.removed)
            if response.accounts:
                accounts_data = response.accounts

            has_more = response.has_more
            cursor = response.next_cursor

    except Exception as e:
        error_str = str(e)
        # Check for ITEM_LOGIN_REQUIRED
        if "ITEM_LOGIN_REQUIRED" in error_str:
            item.error_code = "ITEM_LOGIN_REQUIRED"
            item.last_sync_status = "failed"
            await session.commit()
            return {"error": "ITEM_LOGIN_REQUIRED"}

        item.last_sync_status = "failed"
        await session.commit()
        raise

    # Ensure accounts exist
    account_map = await ensure_plaid_accounts(session, item, accounts_data)

    stats = {"added": 0, "modified": 0, "removed": 0, "deduped": 0, "new_tx_ids": []}

    # Process added transactions
    new_tx_ids = []
    for plaid_tx in all_added:
        plaid_account_id = plaid_tx.account_id
        bank_account_id = account_map.get(plaid_account_id)
        if not bank_account_id:
            continue

        # Check for existing (dedup by plaid_transaction_id)
        existing = await session.execute(
            select(Transaction.id).where(
                Transaction.plaid_transaction_id == plaid_tx.transaction_id
            )
        )
        if existing.scalar_one_or_none():
            continue

        tx_data = map_plaid_transaction(
            plaid_tx, str(bank_account_id), str(item.user_id), str(item.household_id)
        )

        # Check if Plaid flags this as a transfer
        if is_plaid_transfer(plaid_tx):
            tx_data["transaction_type"] = "transfer"

        # Try to match against email transactions
        match = await find_email_match(
            session,
            item.user_id,
            tx_data["raw_merchant_name"],
            tx_data["amount"],
            tx_data["transaction_date"],
        )

        new_tx = Transaction(**tx_data)
        session.add(new_tx)
        await session.flush()

        if match:
            await apply_match_and_delete_emails(
                session, new_tx.id, match["email_tx_ids"], match["enrichment"]
            )
            stats["deduped"] += 1

        new_tx_ids.append(new_tx.id)
        stats["added"] += 1
        stats["new_tx_ids"].append(str(new_tx.id))

    # Process modified transactions (tip adjustments, pending → settled)
    for plaid_tx in all_modified:
        existing = await session.execute(
            select(Transaction).where(
                Transaction.plaid_transaction_id == plaid_tx.transaction_id
            )
        )
        tx = existing.scalar_one_or_none()
        if not tx:
            continue

        plaid_amount = float(plaid_tx.amount)
        tx.amount = plaid_amount * -1
        tx.status = "pending" if plaid_tx.pending else "confirmed"
        tx.raw_merchant_name = plaid_tx.merchant_name or plaid_tx.name or tx.raw_merchant_name
        stats["modified"] += 1

    # Process removed transactions
    for plaid_tx in all_removed:
        await session.execute(
            delete(Transaction).where(
                Transaction.plaid_transaction_id == plaid_tx.transaction_id
            )
        )
        stats["removed"] += 1

    # Update item state
    item.cursor = cursor
    item.last_sync_at = datetime.now(timezone.utc)
    item.last_sync_status = "success"
    item.error_code = None

    await session.commit()

    return stats


async def ensure_plaid_accounts(
    session: AsyncSession,
    item: PlaidItem,
    plaid_accounts: list,
) -> dict[str, uuid.UUID]:
    """Create/update bank_accounts from Plaid accounts. Returns {plaid_account_id: bank_account_id}."""
    account_map: dict[str, uuid.UUID] = {}

    for pa in plaid_accounts:
        plaid_account_id = pa.account_id

        # Check if account already exists
        result = await session.execute(
            select(BankAccount).where(
                BankAccount.plaid_account_id == plaid_account_id,
                BankAccount.plaid_item_id == item.id,
            )
        )
        ba = result.scalar_one_or_none()

        account_kind = map_account_kind(pa.type, pa.subtype)
        account_name = pa.official_name or pa.name or "Unknown Account"
        mask = pa.mask

        if ba:
            # Update balances
            ba.balance_current = int(pa.balances.current * 100) if pa.balances.current is not None else None
            ba.balance_limit = int(pa.balances.limit * 100) if pa.balances.limit is not None else None
            ba.last_synced_at = datetime.now(timezone.utc)
        else:
            # Create new bank account
            ba = BankAccount(
                household_id=item.household_id,
                user_id=item.user_id,
                bank_name=item.institution_name,
                account_type="personal",  # default, user can change
                account_kind=account_kind,
                account_name=account_name,
                account_number=mask,
                currency=pa.balances.iso_currency_code or "USD",
                balance_current=int(pa.balances.current * 100) if pa.balances.current is not None else None,
                balance_limit=int(pa.balances.limit * 100) if pa.balances.limit is not None else None,
                last_synced_at=datetime.now(timezone.utc),
                is_active=True,
                provider="plaid",
                country="US",
                plaid_item_id=item.id,
                plaid_account_id=plaid_account_id,
            )
            session.add(ba)
            await session.flush()

        account_map[plaid_account_id] = ba.id

    return account_map
```

- [ ] **Step 2: Create Plaid router**

Create `backend/modules/plaid/router.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session
from core.security import get_current_user
from jobs.queue import enqueue_job
from modules.plaid.models import PlaidItem
from modules.plaid.service import (
    create_link_token,
    exchange_public_token,
    remove_item,
)
from modules.households.models import BankAccount, HouseholdMember

router = APIRouter(prefix="/plaid", tags=["plaid"])


class ExchangeTokenRequest(BaseModel):
    public_token: str
    institution_id: str
    institution_name: str


@router.post("/create-link-token")
async def create_link_token_endpoint(
    user=Depends(get_current_user),
):
    try:
        token = create_link_token(user.id)
        return {"link_token": token}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create link token: {e}")


@router.post("/exchange-token")
async def exchange_token_endpoint(
    body: ExchangeTokenRequest,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # Get user's household
    result = await session.execute(
        select(HouseholdMember.household_id).where(HouseholdMember.user_id == user.id)
    )
    household_id = result.scalar_one_or_none()
    if not household_id:
        raise HTTPException(status_code=400, detail="User has no household")

    try:
        access_token, item_id = exchange_public_token(body.public_token)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token exchange failed: {e}")

    # Create PlaidItem
    plaid_item = PlaidItem(
        user_id=user.id,
        household_id=household_id,
        plaid_item_id=item_id,
        access_token=access_token,
        institution_id=body.institution_id,
        institution_name=body.institution_name,
    )
    session.add(plaid_item)
    await session.flush()

    # Enqueue initial sync (90-day lookback)
    await enqueue_job("run_plaid_sync_job", plaid_item_id=str(plaid_item.id), initial=True)

    await session.commit()
    return {"plaid_item_id": str(plaid_item.id)}


@router.delete("/disconnect")
async def disconnect_endpoint(
    plaid_item_id: str,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(PlaidItem).where(
            PlaidItem.id == uuid.UUID(plaid_item_id),
            PlaidItem.user_id == user.id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Plaid item not found")

    # Remove from Plaid (stops billing)
    try:
        remove_item(item.access_token)
    except Exception:
        pass  # Best effort — item may already be removed

    # Soft-delete bank accounts (preserve transaction history)
    await session.execute(
        update(BankAccount)
        .where(BankAccount.plaid_item_id == item.id)
        .values(is_active=False)
    )

    # Delete PlaidItem
    await session.delete(item)
    await session.commit()

    return {"success": True}


@router.post("/sync")
async def manual_sync_endpoint(
    plaid_item_id: str,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(PlaidItem).where(
            PlaidItem.id == uuid.UUID(plaid_item_id),
            PlaidItem.user_id == user.id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Plaid item not found")

    await enqueue_job("run_plaid_sync_job", plaid_item_id=str(item.id), initial=False)

    return {"status": "syncing"}
```

- [ ] **Step 3: Update `jobs/queue.py` to accept positional args**

Edit `backend/jobs/queue.py` — change line 6 to accept both `*args` and `**kwargs`:

```python
async def enqueue_job(function_name: str, *args, **kwargs) -> None:
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await redis.enqueue_job(function_name, *args, **kwargs)
    await redis.aclose()
```

- [ ] **Step 4: Add worker functions to `jobs/tasks.py`**

Edit `backend/jobs/tasks.py` — add these functions at the end of the file (after the existing `run_connect_sync` function):

```python
async def run_plaid_sync_job(ctx: dict, plaid_item_id: str, initial: bool = False):
    """Run a Plaid transaction sync for one item."""
    from modules.plaid.sync import run_plaid_sync

    async with AsyncSessionLocal() as db:
        stats = await run_plaid_sync(db, uuid.UUID(plaid_item_id), initial=initial)
        # Trigger merchant review for new transactions
        if stats.get("new_tx_ids"):
            from modules.merchant_review.service import maybe_create_review_job
            await maybe_create_review_job(db, stats["new_tx_ids"])
        return stats


async def schedule_plaid_syncs(ctx: dict):
    """Daily cron: enqueue sync for all active Plaid items."""
    from modules.plaid.models import PlaidItem

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PlaidItem).where(PlaidItem.error_code.is_(None))
        )
        items = result.scalars().all()
        redis = ctx["redis"]
        for item in items:
            await redis.enqueue_job(
                "run_plaid_sync_job",
                plaid_item_id=str(item.id),
                initial=False,
            )
        if items:
            print(f"[SCHEDULE_PLAID_SYNCS] Enqueued {len(items)} syncs", flush=True)


async def run_reconciliation_job(ctx: dict):
    """Daily cron: detect inter-account transfers across all households."""
    from modules.reconciliation.transfers import detect_transfers
    from modules.households.models import Household

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Household.id))
        household_ids = result.scalars().all()
        total = 0
        for hid in household_ids:
            pairs = await detect_transfers(db, hid)
            total += pairs
        await db.commit()
        if total:
            print(f"[RECONCILIATION] Detected {total} transfer pairs", flush=True)
```

- [ ] **Step 5: Update `worker.py` to import and register new functions**

Edit `backend/worker.py`:

1. Add imports (after existing imports at line 13):

```python
from jobs.tasks import (
    run_plaid_sync_job,
    schedule_plaid_syncs,
    run_reconciliation_job,
)
```

2. Add `run_plaid_sync_job` to the `functions` list (line 26):

```python
    functions = [process_email, send_invite_email, run_connect_sync, run_plaid_sync_job]
```

3. Add the new cron jobs (after existing crons, line 32):

```python
        cron(schedule_plaid_syncs, hour=3, minute=30),        # Daily 3:30am UTC — sync all Plaid items
        cron(run_reconciliation_job, hour=6, minute=0),       # Daily 6am UTC — transfer detection
```

Note: Plaid syncs at 3:30am to avoid conflict with `cleanup_processed_webhooks` at 4:00am.

- [ ] **Step 4: Commit**

```bash
git add backend/modules/plaid/sync.py backend/modules/plaid/router.py backend/jobs/tasks.py backend/jobs/queue.py backend/worker.py
git commit -m "feat: add Plaid sync logic, router endpoints, and worker cron jobs"
```

---

## Task 6: Configuration Wiring and Final Integration

**Depends on:** Tasks 2, 5

**Files:**
- Modify: `backend/main.py:66-79` (register plaid router)
- Modify: `backend/.env.example` (add Plaid env vars)

- [ ] **Step 1: Register Plaid router and model in main.py**

Edit `backend/main.py`:

1. Add model import for FK resolution (after line 14, with the other model imports):

```python
import modules.plaid.models  # noqa: F401
```

2. Add router import (after line 28, with the other router imports):

```python
from modules.plaid.router import router as plaid_router
```

3. Add router registration in `create_app()` (after line 79):

```python
    app.include_router(plaid_router)
```

- [ ] **Step 2: Update .env.example**

Edit `backend/.env.example` — add at the end:

```
# Plaid (US bank connections)
PLAID_CLIENT_ID=your_plaid_client_id
PLAID_SECRET=your_plaid_sandbox_secret
PLAID_ENV=sandbox
```

- [ ] **Step 3: Verify the backend starts without errors**

```bash
cd backend && python -c "from main import create_app; app = create_app(); print('App created with routes:', [r.path for r in app.routes if hasattr(r, 'path')])"
```

Expected: No import errors, Plaid routes visible in output.

- [ ] **Step 4: Commit**

```bash
git add backend/main.py backend/.env.example
git commit -m "feat: wire up Plaid router and add env config"
```

- [ ] **Step 5: Final integration commit**

```bash
git log --oneline -6
```

Verify all commits are present:
1. Migration 023
2. Plaid module foundations (models, service, mapper)
3. Shared reconciliation utility
4. Frontend (country selector, Plaid Link, flags)
5. Plaid sync + router + worker
6. Config wiring

---

## Post-Implementation Notes

**Testing with Plaid Sandbox:**
- Use credentials `user_good` / `pass_good` in Plaid Link sandbox
- Sandbox returns realistic fake transaction data
- No billing in sandbox mode

**To go live:**
1. Set `PLAID_ENV=production` and use production secret
2. First 200 API calls are free (Limited Production)
3. Remove manual sync button when testing is complete

**Future enhancements (not in scope):**
- Plaid webhook-driven sync (reduce to real-time)
- Multi-currency budget support (USD + CLP)
