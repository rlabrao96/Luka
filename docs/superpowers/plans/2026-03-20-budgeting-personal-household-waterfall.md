# Budgeting: Personal + Household Waterfall — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-bar budget page with a three-layer waterfall view: income → household → personal ceiling, with a 50/20/30-style allocation editor and a cumulative spending pace chart.

**Architecture:** Extend `transactions` with `transaction_type` (expense/income/transfer) and add a `household_budget_allocations` table. A new Fintoc classifier module detects inflows/transfers. Three new backend services handle the waterfall calculation, allocation CRUD, and pace data. The frontend gains a PaceChart (Recharts), AllocationCard (sliders), and WaterfallCards (progress bars).

**Tech Stack:** FastAPI · SQLAlchemy async 2.0 · Alembic · pytest-asyncio · Next.js 16 App Router · TanStack Query 5 · Recharts · Tailwind CSS 4 · shadcn/ui

---

## Parallel Execution Map

```
Phase 1: Task 1 (Migration + Models)               ← sequential, everything depends on this
          ↓
Phase 2: Task 2A      Task 2B          Task 2C      ← dispatch all 3 in parallel
         Classifier   Personal svc     Allocation svc
         (classifier.py only)  (personal_service.py only)  (allocation_service.py only)
          ↓
         Task 2D (Schemas + Router)                 ← sequential, after 2A/2B/2C
          ↓
          Verification Checkpoint 1 (backend)       ← single verifier agent
          ↓
Phase 3: Task 3A (Types + Hooks)              ← sequential within frontend
          ↓
         Task 3B  Task 3C  Task 3D            ← dispatch all 3 in parallel
         PaceChart AllocationCard WaterfallCards
          ↓
         Task 3E (Budgets page wires all)     ← sequential, depends on 3B/3C/3D
          ↓
          Verification Checkpoint 2 (frontend) ← single verifier agent
          ↓
Phase 4: Task 4 (Final integration commit)
```

---

## File Map

**New backend files:**
- `backend/alembic/versions/011_transaction_type_budget_allocations.py`
- `backend/modules/fintoc/classifier.py` — pure classification logic (no DB, fully unit-testable)
- `backend/modules/budgets/personal_service.py` — waterfall + pace queries
- `backend/modules/budgets/allocation_service.py` — allocation CRUD + suggestion logic
- `backend/tests/test_fintoc_classifier.py`
- `backend/tests/test_budget_personal_service.py`
- `backend/tests/test_budget_allocation_service.py`

**Modified backend files:**
- `backend/modules/transactions/models.py` — add `transaction_type`, `transfer_to_account_id`
- `backend/modules/households/models.py` — add `HouseholdBudgetAllocation`
- `backend/modules/fintoc/client.py` — add `counterparty_account_id`, remove debit-only filter
- `backend/modules/fintoc/reconciler.py` — pass `transaction_type` through to insert
- `backend/jobs/tasks.py` — use classifier in both `run_fintoc_sync` + `import_fintoc_history`
- `backend/modules/budgets/router.py` — add 3 new endpoints
- `backend/modules/budgets/schemas.py` — new Pydantic schemas

**New frontend files:**
- `frontend/app/(dashboard)/components/PaceChart.tsx`
- `frontend/app/(dashboard)/components/AllocationCard.tsx`
- `frontend/app/(dashboard)/components/WaterfallCards.tsx`

**Modified frontend files:**
- `frontend/app/lib/api.ts` — new types + 3 new API methods
- `frontend/app/lib/hooks/useBudget.ts` — add `usePersonalBudget`, `useAllocation`, `useSaveAllocation`
- `frontend/app/(dashboard)/budgets/page.tsx` — full rewrite

---

## Phase 1 — Task 1: Data Foundation

> **Must complete before any other task. Run alone.**

**Files:**
- Create: `backend/alembic/versions/011_transaction_type_budget_allocations.py`
- Modify: `backend/modules/transactions/models.py`
- Modify: `backend/modules/households/models.py`

- [ ] **Step 1.1: Write the Alembic migration**

```python
# backend/alembic/versions/011_transaction_type_budget_allocations.py
"""transaction_type and household_budget_allocations

Revision ID: 011
Revises: 010
Create Date: 2026-03-20
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "011"
down_revision: Union[str, Sequence[str], None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add transaction_type to transactions
    op.add_column(
        "transactions",
        sa.Column(
            "transaction_type",
            sa.String(10),
            nullable=False,
            server_default="expense",
        ),
    )
    op.create_check_constraint(
        "ck_transaction_type",
        "transactions",
        "transaction_type IN ('expense', 'income', 'transfer')",
    )

    # 2. Add transfer_to_account_id to transactions
    op.add_column(
        "transactions",
        sa.Column(
            "transfer_to_account_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bank_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # 3. Create household_budget_allocations table
    op.create_table(
        "household_budget_allocations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("household_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("hogar_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("ahorro_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("personal_pct", sa.Numeric(5, 2), nullable=False),
        sa.UniqueConstraint("household_id", "month", name="uq_budget_allocation_household_month"),
        sa.CheckConstraint("hogar_pct + ahorro_pct + personal_pct = 100", name="ck_pct_sum"),
    )


def downgrade() -> None:
    op.drop_table("household_budget_allocations")
    op.drop_column("transactions", "transfer_to_account_id")
    op.drop_constraint("ck_transaction_type", "transactions", type_="check")
    op.drop_column("transactions", "transaction_type")
```

- [ ] **Step 1.2: Add `transaction_type` and `transfer_to_account_id` to `Transaction` model**

In `backend/modules/transactions/models.py`, add after the `fintoc_id` field:

```python
transaction_type: Mapped[str] = mapped_column(String(10), nullable=False, default="expense")
transfer_to_account_id: Mapped[uuid.UUID | None] = mapped_column(
    ForeignKey("bank_accounts.id", ondelete="SET NULL"), nullable=True
)
```

- [ ] **Step 1.3: Add `HouseholdBudgetAllocation` model to `households/models.py`**

```python
class HouseholdBudgetAllocation(Base):
    __tablename__ = "household_budget_allocations"
    __table_args__ = (
        UniqueConstraint("household_id", "month", name="uq_budget_allocation_household_month"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    month: Mapped[date] = mapped_column(Date, nullable=False)
    hogar_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    ahorro_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    personal_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 1.4: Run migration locally**

```bash
cd backend && python3 -m alembic upgrade head
```

Expected: `Running upgrade 010 -> 011, transaction_type and household_budget_allocations`

- [ ] **Step 1.5: Verify migration applied**

```bash
cd backend && python3 -m alembic current
```

Expected: `011 (head)`

- [ ] **Step 1.6: Commit**

```bash
git add backend/alembic/versions/011_transaction_type_budget_allocations.py \
        backend/modules/transactions/models.py \
        backend/modules/households/models.py
git commit -m "feat(db): add transaction_type, transfer_to_account_id, household_budget_allocations"
```

---

## Phase 2A — Task 2A: Fintoc Classifier

> **Parallel with 2B and 2C. Requires Phase 1 complete.**

**Files:**
- Create: `backend/modules/fintoc/classifier.py`
- Create: `backend/tests/test_fintoc_classifier.py`
- Modify: `backend/modules/fintoc/client.py`
- Modify: `backend/modules/fintoc/reconciler.py`
- Modify: `backend/jobs/tasks.py`

- [ ] **Step 2A.1: Write failing classifier tests**

```python
# backend/tests/test_fintoc_classifier.py
import pytest
from datetime import datetime
from modules.fintoc.classifier import classify_movement, MovementClassification, ClassificationResult
from modules.fintoc.client import FintocTransaction


def _txn(amount: int, description: str = "SUPERMERCADO", fintoc_id: str = "f1",
         account_id: str = "acc1", counterparty_id: str | None = None) -> FintocTransaction:
    return FintocTransaction(
        id=fintoc_id,
        amount=amount,
        description=description,
        transaction_date=datetime(2026, 3, 10),
        account_id=account_id,
        counterparty_account_id=counterparty_id,
    )


# --- Income classification ---

def test_positive_amount_no_keywords_is_income():
    result = classify_movement(_txn(500000), household_fintoc_ids=[], all_movements=[])
    assert result.classification == MovementClassification.INCOME
    assert result.matched_fintoc_account_id is None


def test_negative_amount_no_match_is_expense():
    result = classify_movement(_txn(-45000), household_fintoc_ids=[], all_movements=[])
    assert result.classification == MovementClassification.EXPENSE
    assert result.matched_fintoc_account_id is None


# --- Transfer via counterparty ID ---

def test_outflow_with_counterparty_id_matching_household_is_transfer():
    result = classify_movement(
        _txn(-200000, counterparty_id="acc_joint"),
        household_fintoc_ids=["acc_joint"],
        all_movements=[],
    )
    assert result.classification == MovementClassification.TRANSFER
    assert result.matched_fintoc_account_id == "acc_joint"


def test_inflow_with_counterparty_id_matching_household_is_inbound_transfer_skip():
    result = classify_movement(
        _txn(200000, counterparty_id="acc_personal"),
        household_fintoc_ids=["acc_personal"],
        all_movements=[],
    )
    assert result.classification == MovementClassification.INBOUND_TRANSFER_SKIP
    assert result.matched_fintoc_account_id == "acc_personal"


# --- Transfer via keyword + amount symmetry fallback ---

def test_outflow_transferencia_keyword_with_symmetric_inbound_is_transfer():
    outflow = _txn(-150000, description="TRANSFERENCIA A CUENTA", account_id="acc1")
    inbound = _txn(150000, description="TRANSFERENCIA RECIBIDA", account_id="acc2")
    result = classify_movement(outflow, household_fintoc_ids=[], all_movements=[inbound])
    assert result.classification == MovementClassification.TRANSFER
    assert result.matched_fintoc_account_id == "acc2"  # sibling account_id


def test_outflow_transferencia_keyword_no_symmetric_match_is_expense():
    outflow = _txn(-150000, description="TRANSFERENCIA A TERCERO", account_id="acc1")
    result = classify_movement(outflow, household_fintoc_ids=[], all_movements=[])
    assert result.classification == MovementClassification.EXPENSE


def test_inflow_traspaso_keyword_with_symmetric_outbound_is_inbound_skip():
    inflow = _txn(80000, description="TRASPASO RECIBIDO", account_id="acc2")
    outbound = _txn(-80000, description="TRASPASO REALIZADO", account_id="acc1")
    result = classify_movement(inflow, household_fintoc_ids=[], all_movements=[outbound])
    assert result.classification == MovementClassification.INBOUND_TRANSFER_SKIP
    assert result.matched_fintoc_account_id == "acc1"
```

- [ ] **Step 2A.2: Run tests — confirm they fail**

```bash
cd backend && python3 -m pytest tests/test_fintoc_classifier.py -v 2>&1 | head -30
```

Expected: `ImportError` or `ModuleNotFoundError` on `classifier`

- [ ] **Step 2A.3: Update `FintocTransaction` dataclass in `client.py`**

Add `counterparty_account_id: str | None = None` to the dataclass and update `fetch_transactions`:

```python
@dataclass
class FintocTransaction:
    id: str
    amount: int          # signed: negative = outflow, positive = inflow
    description: str
    transaction_date: datetime
    account_id: str
    counterparty_account_id: str | None = None
```

Remove the `if int(mov.get("amount", 0)) < 0` debit-only filter. Return **all** movements (positive and negative). Update `abs(int(mov["amount"]))` to preserve sign: `amount=int(mov["amount"])`. Attempt to populate `counterparty_account_id` from `mov.get("recipient_account", {}).get("id")` or `mov.get("sender_account", {}).get("id")` (whichever is present).

Full updated return block:

```python
return [
    FintocTransaction(
        id=mov["id"],
        amount=int(mov["amount"]),           # signed — negative=outflow, positive=inflow
        description=(mov.get("description") or "").upper().strip(),
        transaction_date=datetime.fromisoformat(mov["post_date"]),
        account_id=account_id,
        counterparty_account_id=(
            mov.get("recipient_account", {}).get("id")
            or mov.get("sender_account", {}).get("id")
        ),
    )
    for mov in all_movements
]
```

- [ ] **Step 2A.4: Implement `classifier.py`**

`classify_movement` returns a `ClassificationResult` so callers can retrieve the matched account Fintoc ID (needed to resolve `transfer_to_account_id`).

```python
# backend/modules/fintoc/classifier.py
from dataclasses import dataclass
from enum import Enum
from modules.fintoc.client import FintocTransaction

_TRANSFER_KEYWORDS = {"TRANSFERENCIA", "TRASPASO"}
_DATE_WINDOW_DAYS = 1


class MovementClassification(str, Enum):
    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"
    INBOUND_TRANSFER_SKIP = "inbound_transfer_skip"  # inbound leg — skip, don't record


@dataclass
class ClassificationResult:
    classification: MovementClassification
    matched_fintoc_account_id: str | None = None  # set when a household sibling matched


def classify_movement(
    movement: FintocTransaction,
    household_fintoc_ids: list[str],
    all_movements: list[FintocTransaction],
) -> ClassificationResult:
    """
    Classify a Fintoc movement. Returns ClassificationResult with:
    - classification: the movement type
    - matched_fintoc_account_id: the sibling Fintoc account ID if a transfer was detected
      (callers use this to resolve bank_accounts.id via DB lookup)
    """
    is_inflow = movement.amount > 0

    # --- Path 1: structured counterparty ID ---
    if movement.counterparty_account_id and movement.counterparty_account_id in household_fintoc_ids:
        cls = MovementClassification.INBOUND_TRANSFER_SKIP if is_inflow else MovementClassification.TRANSFER
        return ClassificationResult(classification=cls, matched_fintoc_account_id=movement.counterparty_account_id)

    # --- Path 2: keyword + amount symmetry ---
    description_words = set(movement.description.split())
    has_transfer_keyword = bool(description_words & _TRANSFER_KEYWORDS)

    if has_transfer_keyword:
        mirror_amount = -movement.amount  # opposite sign
        for other in all_movements:
            if other.id == movement.id:
                continue
            if other.account_id == movement.account_id:
                continue  # same account — not a sibling
            if other.amount != mirror_amount:
                continue
            date_delta = abs((movement.transaction_date - other.transaction_date).days)
            if date_delta <= _DATE_WINDOW_DAYS:
                cls = (
                    MovementClassification.INBOUND_TRANSFER_SKIP
                    if is_inflow
                    else MovementClassification.TRANSFER
                )
                return ClassificationResult(classification=cls, matched_fintoc_account_id=other.account_id)

    # --- Default ---
    cls = MovementClassification.INCOME if is_inflow else MovementClassification.EXPENSE
    return ClassificationResult(classification=cls)
```

- [ ] **Step 2A.5: Run classifier tests — confirm they pass**

```bash
cd backend && python3 -m pytest tests/test_fintoc_classifier.py -v
```

Expected: All 8 tests PASS

- [ ] **Step 2A.6: Update `reconciler.py` to pass `transaction_type` through**

In `reconcile_transactions`, the unmatched insert must receive `transaction_type`. Since `reconcile_transactions` is called after classification (see Task 2A.7), change the unmatched insert to accept an optional `transaction_type` parameter:

```python
async def reconcile_transactions(
    fintoc_transactions: list[FintocTransaction],
    db,
    user_id,
    household_id,
    transaction_types: dict[str, str] | None = None,  # fintoc_id -> 'expense'|'income'|'transfer'
) -> dict:
    ...
    # In the unmatched branch:
    txn_type = (transaction_types or {}).get(ftc_txn.id, "expense")
    new_txn = Transaction(
        ...
        transaction_type=txn_type,
        fintoc_id=ftc_txn.id,
    )
```

- [ ] **Step 2A.7: Update `run_fintoc_sync` in `tasks.py` to use classifier**

Add imports at top of function:
```python
from modules.fintoc.classifier import classify_movement, MovementClassification
```

Inside `run_fintoc_sync`, **replace** the block starting with `client = FintocClient(...)` through the end of the `try` block with:

```python
client = FintocClient(link_token=account.fintoc_link_id)
all_movements = await client.fetch_transactions(
    account_id=account.fintoc_account_id,
    since=since,
    until=date.today(),
)

# Build sibling fintoc account IDs for transfer detection
sibling_result = await db.execute(
    select(BankAccount.fintoc_account_id, BankAccount.id).where(
        BankAccount.household_id == account.household_id,
        BankAccount.fintoc_account_id.isnot(None),
    )
)
fintoc_id_to_db_id: dict[str, uuid.UUID] = {
    row.fintoc_account_id: row.id for row in sibling_result
}
household_fintoc_ids = list(fintoc_id_to_db_id.keys())

expense_txns = []
for txn in all_movements:
    result = classify_movement(txn, household_fintoc_ids, all_movements=all_movements)
    if result.classification == MovementClassification.INBOUND_TRANSFER_SKIP:
        continue
    elif result.classification == MovementClassification.EXPENSE:
        expense_txns.append(txn)
    else:
        existing = await db.scalar(select(Transaction).where(Transaction.fintoc_id == txn.id))
        if not existing:
            # Resolve matched Fintoc account ID → internal bank_accounts.id
            transfer_to = (
                fintoc_id_to_db_id.get(result.matched_fintoc_account_id)
                if result.matched_fintoc_account_id else None
            )
            new_txn = Transaction(
                user_id=account.user_id,
                household_id=account.household_id,
                bank_account_id=account.id,
                raw_merchant_name=txn.description,
                amount=abs(txn.amount),
                currency="CLP",
                transaction_date=txn.transaction_date,
                source="fintoc",
                status="settled",
                fintoc_id=txn.id,
                transaction_type=result.classification.value,
                transfer_to_account_id=transfer_to,
            )
            db.add(new_txn)

await reconcile_transactions(
    expense_txns, db,
    user_id=account.user_id,
    household_id=account.household_id,
    transaction_types={t.id: "expense" for t in expense_txns},
)
account.last_synced_at = datetime.now(timezone.utc)
await db.commit()
```

- [ ] **Step 2A.8: Replace the entire `for ftxn in fintoc_txns:` loop in `import_fintoc_history`**

> ⚠️ This is a **full replacement** of the existing loop (lines 365–405 of the original `tasks.py`). Do not add guards inside the old loop — replace it entirely.

Before the loop, add the same `fintoc_id_to_db_id` lookup as in 2A.7, then replace the full `for ftxn in fintoc_txns:` block with:

```python
# Build sibling fintoc account IDs for transfer detection
sibling_result = await db.execute(
    select(BankAccount.fintoc_account_id, BankAccount.id).where(
        BankAccount.household_id == account.household_id,
        BankAccount.fintoc_account_id.isnot(None),
    )
)
fintoc_id_to_db_id: dict[str, uuid.UUID] = {
    row.fintoc_account_id: row.id for row in sibling_result
}
household_fintoc_ids = list(fintoc_id_to_db_id.keys())

for ftxn in fintoc_txns:
    existing = await db.scalar(
        select(Transaction).where(Transaction.fintoc_id == ftxn.id)
    )
    if existing:
        skipped += 1
        continue

    cls_result = classify_movement(ftxn, household_fintoc_ids, all_movements=fintoc_txns)
    if cls_result.classification == MovementClassification.INBOUND_TRANSFER_SKIP:
        skipped += 1
        continue

    try:
        transfer_to = (
            fintoc_id_to_db_id.get(cls_result.matched_fintoc_account_id)
            if cls_result.matched_fintoc_account_id else None
        )
        txn = Transaction(
            user_id=account.user_id,
            household_id=account.household_id,
            bank_account_id=account.id,
            raw_merchant_name=ftxn.description,
            amount=abs(ftxn.amount),
            currency="CLP",
            transaction_date=ftxn.transaction_date,
            source="fintoc",
            status="settled",
            fintoc_id=ftxn.id,
            transaction_type=cls_result.classification.value,  # explicit — do NOT rely on DEFAULT
            transfer_to_account_id=transfer_to,
        )
        db.add(txn)
        await db.flush()

        # Only create TransactionSplit for expense transactions
        if cls_result.classification == MovementClassification.EXPENSE:
            split = TransactionSplit(
                transaction_id=txn.id,
                split_type=split_map.get(account.account_type, "personal"),
                decided_by_user_id=account.user_id,
                decided_at=datetime.now(timezone.utc),
            )
            db.add(split)

        await db.commit()
        imported += 1
    except Exception as loop_err:
        await db.rollback()
        logger.warning(
            "import_fintoc_history: skipping txn fintoc_id=%s due to error: %s",
            ftxn.id, loop_err,
        )
        skipped += 1
```

- [ ] **Step 2A.9: Run all existing tests — confirm nothing broken**

```bash
cd backend && python3 -m pytest tests/ -v --ignore=tests/test_fintoc_classifier.py 2>&1 | tail -20
```

Expected: All previously passing tests still PASS

- [ ] **Step 2A.10: Commit**

```bash
git add backend/modules/fintoc/classifier.py \
        backend/modules/fintoc/client.py \
        backend/modules/fintoc/reconciler.py \
        backend/jobs/tasks.py \
        backend/tests/test_fintoc_classifier.py
git commit -m "feat(fintoc): classifier for income/transfer/expense movement detection"
```

---

## Phase 2B — Task 2B: Personal Budget Service + Endpoint

> **Parallel with 2A and 2C. Requires Phase 1 complete.**

**Files:**
- Create: `backend/modules/budgets/personal_service.py`
- Create: `backend/tests/test_budget_personal_service.py`
- Modify: `backend/modules/budgets/schemas.py`
- Modify: `backend/modules/budgets/router.py`

- [ ] **Step 2B.1: Write failing personal service tests**

```python
# backend/tests/test_budget_personal_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date
from modules.budgets.personal_service import (
    compute_personal_budget,
    compute_pace,
)


def test_compute_pace_under_budget():
    pace = compute_pace(
        spendable_budget=1_000_000,
        daily_cumulative={1: 0, 2: 10000, 3: 25000, 4: 25000, 5: 50000},
        today_day=5,
        days_in_month=30,
    )
    assert pace["today_day"] == 5
    assert pace["days_in_month"] == 30
    assert pace["pace_at_today"] == pytest.approx(1_000_000 * 5 / 30, rel=0.01)
    assert pace["actual_at_today"] == 50000
    assert pace["delta"] < 0  # under budget
    assert pace["on_track"] is True


def test_compute_pace_over_budget():
    pace = compute_pace(
        spendable_budget=500_000,
        daily_cumulative={1: 100000, 2: 200000, 3: 350000},
        today_day=3,
        days_in_month=30,
    )
    assert pace["on_track"] is False
    assert pace["delta"] > 0


def test_compute_pace_zero_spendable_budget():
    pace = compute_pace(
        spendable_budget=0,
        daily_cumulative={},
        today_day=5,
        days_in_month=30,
    )
    assert pace["pace_at_today"] == 0
    assert pace["on_track"] is True


def test_personal_ceiling_uses_allocation_when_set():
    """When allocation exists, ceiling = income * personal_pct / 100."""
    result = _compute_ceiling(
        income=2_000_000,
        user_deposited=400_000,
        personal_pct=30.0,
        allocation_exists=True,
    )
    assert result == pytest.approx(600_000)


def test_personal_ceiling_uses_waterfall_when_no_allocation():
    """When no allocation, ceiling = income - user_deposited."""
    result = _compute_ceiling(
        income=2_000_000,
        user_deposited=400_000,
        personal_pct=30.0,
        allocation_exists=False,
    )
    assert result == pytest.approx(1_600_000)


def test_personal_ceiling_clamped_when_negative():
    from modules.budgets.personal_service import build_personal_block
    block = build_personal_block(
        ceiling=-100_000,
        spent=200_000,
        breakdown_household=100_000,
        breakdown_personal=100_000,
    )
    assert block["ceiling_clamped"] is True
    assert block["available"] == -200_000
    assert block["percent_used"] is None


def test_personal_ceiling_percent_used_null_when_zero():
    from modules.budgets.personal_service import build_personal_block
    block = build_personal_block(
        ceiling=0,
        spent=0,
        breakdown_household=0,
        breakdown_personal=0,
    )
    assert block["percent_used"] is None


# Helper
def _compute_ceiling(income, user_deposited, personal_pct, allocation_exists):
    from modules.budgets.personal_service import compute_personal_ceiling
    return compute_personal_ceiling(
        income=income,
        user_deposited=user_deposited,
        personal_pct=personal_pct,
        allocation_exists=allocation_exists,
        mode="waterfall",
    )
```

- [ ] **Step 2B.2: Run tests — confirm they fail**

```bash
cd backend && python3 -m pytest tests/test_budget_personal_service.py -v 2>&1 | head -20
```

Expected: `ImportError` on `personal_service`

- [ ] **Step 2B.3: Implement `personal_service.py`**

```python
# backend/modules/budgets/personal_service.py
import uuid
import calendar
from datetime import date, datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from modules.transactions.models import Transaction, TransactionSplit
from modules.households.models import BankAccount, HouseholdBudgetAllocation, Household


def compute_personal_ceiling(
    income: float,
    user_deposited: float,
    personal_pct: float | None,
    allocation_exists: bool,
    mode: str,
) -> float:
    if allocation_exists and personal_pct is not None:
        return income * personal_pct / 100
    if mode == "waterfall":
        return income - user_deposited
    return income  # single mode


def build_personal_block(
    ceiling: float,
    spent: float,
    breakdown_household: float,
    breakdown_personal: float,
) -> dict:
    clamped = ceiling < 0
    available = ceiling - spent if not clamped else -spent
    pct_used = round(spent / ceiling * 100, 1) if ceiling > 0 else None
    return {
        "ceiling": ceiling,
        "ceiling_clamped": clamped,
        "spent": spent,
        "breakdown": {
            "household": breakdown_household,
            "personal": breakdown_personal,
        },
        "available": available,
        "percent_used": pct_used,
    }


def compute_pace(
    spendable_budget: float,
    daily_cumulative: dict[int, float],
    today_day: int,
    days_in_month: int,
) -> dict:
    pace_at_today = (
        spendable_budget * today_day / days_in_month if days_in_month > 0 else 0
    )
    actual_at_today = daily_cumulative.get(today_day, 0.0)
    delta = actual_at_today - pace_at_today
    daily_points = [
        {"day": d, "cumulative_spent": daily_cumulative.get(d, 0.0)}
        for d in range(1, today_day + 1)
    ]
    return {
        "spendable_budget": spendable_budget,
        "daily_points": daily_points,
        "today_day": today_day,
        "days_in_month": days_in_month,
        "pace_at_today": round(pace_at_today, 0),
        "actual_at_today": actual_at_today,
        "delta": round(delta, 0),
        "on_track": delta <= 0,
    }


async def get_personal_budget(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    month: date,
) -> dict:
    first_day = datetime(month.year, month.month, 1, tzinfo=timezone.utc)
    last_day_num = calendar.monthrange(month.year, month.month)[1]
    next_month_year = month.year + 1 if month.month == 12 else month.year
    next_month_num = 1 if month.month == 12 else month.month + 1
    first_day_next = datetime(next_month_year, next_month_num, 1, tzinfo=timezone.utc)
    today = datetime.now(timezone.utc)
    today_day = min(today.day, last_day_num) if today.year == month.year and today.month == month.month else last_day_num

    # Mode detection
    household = await db.get(Household, household_id)
    mode = "single" if household.type == "individual" else "waterfall"

    # Allocation
    alloc_result = await db.execute(
        select(HouseholdBudgetAllocation).where(
            HouseholdBudgetAllocation.household_id == household_id,
            HouseholdBudgetAllocation.month == month,
        )
    )
    allocation = alloc_result.scalar_one_or_none()
    alloc_exists = allocation is not None
    hogar_pct = float(allocation.hogar_pct) if allocation else 50.0
    ahorro_pct = float(allocation.ahorro_pct) if allocation else 20.0
    personal_pct = float(allocation.personal_pct) if allocation else 30.0

    # Income — requesting user's personal accounts
    personal_account_ids_result = await db.execute(
        select(BankAccount.id).where(
            BankAccount.user_id == user_id,
            BankAccount.household_id == household_id,
            BankAccount.account_type == "personal",
            BankAccount.is_active.is_(True),
        )
    )
    personal_account_ids = list(personal_account_ids_result.scalars().all())

    income_result = await db.execute(
        select(func.sum(Transaction.amount)).where(
            Transaction.bank_account_id.in_(personal_account_ids),
            Transaction.transaction_type == "income",
            Transaction.transaction_date >= first_day,
            Transaction.transaction_date < first_day_next,
        )
    )
    income = float(income_result.scalar() or 0)

    # User's own deposits to joint (for ceiling when no allocation)
    user_deposited_result = await db.execute(
        select(func.sum(Transaction.amount)).where(
            Transaction.bank_account_id.in_(personal_account_ids),
            Transaction.transaction_type == "transfer",
            Transaction.transaction_date >= first_day,
            Transaction.transaction_date < first_day_next,
        )
    )
    user_deposited = float(user_deposited_result.scalar() or 0)

    # Household block (waterfall only)
    household_block = None
    if mode == "waterfall":
        # Total deposits from all members to joint
        all_member_accounts_result = await db.execute(
            select(BankAccount.id).where(
                BankAccount.household_id == household_id,
                BankAccount.account_type == "personal",
                BankAccount.is_active.is_(True),
            )
        )
        all_personal_ids = list(all_member_accounts_result.scalars().all())

        total_deposited_result = await db.execute(
            select(func.sum(Transaction.amount)).where(
                Transaction.bank_account_id.in_(all_personal_ids),
                Transaction.transaction_type == "transfer",
                Transaction.transaction_date >= first_day,
                Transaction.transaction_date < first_day_next,
            )
        )
        total_deposited = float(total_deposited_result.scalar() or 0)

        # Household spending (shared splits on joint accounts)
        joint_account_ids_result = await db.execute(
            select(BankAccount.id).where(
                BankAccount.household_id == household_id,
                BankAccount.account_type == "joint",
                BankAccount.is_active.is_(True),
            )
        )
        joint_ids = list(joint_account_ids_result.scalars().all())

        household_spent_result = await db.execute(
            select(func.sum(Transaction.amount))
            .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
            .where(
                Transaction.household_id == household_id,
                Transaction.transaction_date >= first_day,
                Transaction.transaction_date < first_day_next,
                TransactionSplit.split_type == "shared",
                Transaction.transaction_type == "expense",
            )
        )
        household_spent = float(household_spent_result.scalar() or 0)

        if total_deposited > 0:
            household_block = {
                "deposited": total_deposited,
                "spent": household_spent,
                "available": total_deposited - household_spent,
                "percent_used": round(household_spent / total_deposited * 100, 1),
            }
        else:
            household_block = {
                "deposited": None,
                "spent": household_spent,
                "available": None,
                "percent_used": None,
            }

    # Personal spending breakdown
    personal_shared_result = await db.execute(
        select(func.sum(Transaction.amount))
        .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .where(
            Transaction.bank_account_id.in_(personal_account_ids),
            Transaction.transaction_type == "expense",
            TransactionSplit.split_type == "shared",
            Transaction.transaction_date >= first_day,
            Transaction.transaction_date < first_day_next,
        )
    )
    breakdown_household = float(personal_shared_result.scalar() or 0)

    personal_only_result = await db.execute(
        select(func.sum(Transaction.amount))
        .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .where(
            Transaction.bank_account_id.in_(personal_account_ids),
            Transaction.transaction_type == "expense",
            TransactionSplit.split_type == "personal",
            Transaction.transaction_date >= first_day,
            Transaction.transaction_date < first_day_next,
        )
    )
    breakdown_personal = float(personal_only_result.scalar() or 0)

    ceiling = compute_personal_ceiling(income, user_deposited, personal_pct, alloc_exists, mode)
    personal_block = build_personal_block(
        ceiling=ceiling,
        spent=breakdown_household + breakdown_personal,
        breakdown_household=breakdown_household,
        breakdown_personal=breakdown_personal,
    )

    # Pace
    all_spending_result = await db.execute(
        select(
            func.date_part("day", Transaction.transaction_date).label("day"),
            func.sum(Transaction.amount).label("total"),
        )
        .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .where(
            Transaction.bank_account_id.in_(personal_account_ids),
            Transaction.transaction_type == "expense",
            Transaction.transaction_date >= first_day,
            Transaction.transaction_date < first_day_next,
        )
        .group_by(func.date_part("day", Transaction.transaction_date))
    )
    daily_raw = {int(row.day): float(row.total) for row in all_spending_result}

    # Build cumulative
    cumulative: dict[int, float] = {}
    running = 0.0
    for d in range(1, today_day + 1):
        running += daily_raw.get(d, 0.0)
        cumulative[d] = running

    spendable = income * (1 - ahorro_pct / 100)
    pace_block = compute_pace(
        spendable_budget=spendable,
        daily_cumulative=cumulative,
        today_day=today_day,
        days_in_month=last_day_num,
    )

    response = {
        "mode": mode,
        "month": month.isoformat(),
        "income": income,
        "personal": personal_block,
        "pace": pace_block,
    }
    if household_block is not None:
        response["household"] = household_block

    return response
```

- [ ] **Step 2B.4: Run personal service tests — confirm they pass**

```bash
cd backend && python3 -m pytest tests/test_budget_personal_service.py -v
```

Expected: All tests PASS

- [ ] **Step 2B.5: Run full test suite**

```bash
cd backend && python3 -m pytest tests/ -v 2>&1 | tail -20
```

Expected: All tests PASS

- [ ] **Step 2B.6: Commit**

```bash
git add backend/modules/budgets/personal_service.py \
        backend/tests/test_budget_personal_service.py
git commit -m "feat(budgets): personal budget waterfall + pace service"
```

---

## Phase 2C — Task 2C: Allocation Service + Endpoint

> **Parallel with 2A and 2B. Requires Phase 1 complete.**

**Files:**
- Create: `backend/modules/budgets/allocation_service.py`
- Create: `backend/tests/test_budget_allocation_service.py`
- Modify: `backend/modules/budgets/schemas.py`
- Modify: `backend/modules/budgets/router.py`

- [ ] **Step 2C.1: Write failing allocation service tests**

```python
# backend/tests/test_budget_allocation_service.py
import pytest
from modules.budgets.allocation_service import (
    compute_historical_suggestion,
    DEFAULT_ALLOCATION,
)


def test_default_allocation_sums_to_100():
    a = DEFAULT_ALLOCATION
    assert a["hogar_pct"] + a["ahorro_pct"] + a["personal_pct"] == 100


def test_historical_suggestion_rounds_to_nearest_5():
    # Simulate: over 3 months, 55% hogar, 35% personal, 10% ahorro
    suggestion = compute_historical_suggestion(
        monthly_data=[
            {"income": 1_000_000, "hogar_spent": 550_000, "personal_spent": 350_000},
            {"income": 1_200_000, "hogar_spent": 660_000, "personal_spent": 420_000},
            {"income": 900_000, "hogar_spent": 495_000, "personal_spent": 315_000},
        ]
    )
    assert suggestion is not None
    assert suggestion["hogar_pct"] + suggestion["ahorro_pct"] + suggestion["personal_pct"] == 100
    # All percentages are multiples of 5
    assert suggestion["hogar_pct"] % 5 == 0
    assert suggestion["ahorro_pct"] % 5 == 0
    assert suggestion["personal_pct"] % 5 == 0


def test_historical_suggestion_returns_none_when_no_income_data():
    suggestion = compute_historical_suggestion(monthly_data=[])
    assert suggestion is None


def test_historical_suggestion_excludes_zero_income_months():
    # 2 valid months + 1 with zero income
    suggestion = compute_historical_suggestion(
        monthly_data=[
            {"income": 1_000_000, "hogar_spent": 500_000, "personal_spent": 300_000},
            {"income": 0, "hogar_spent": 0, "personal_spent": 0},  # skip
            {"income": 800_000, "hogar_spent": 400_000, "personal_spent": 240_000},
        ]
    )
    assert suggestion is not None
```

- [ ] **Step 2C.2: Run tests — confirm they fail**

```bash
cd backend && python3 -m pytest tests/test_budget_allocation_service.py -v 2>&1 | head -20
```

Expected: `ImportError` on `allocation_service`

- [ ] **Step 2C.3: Implement `allocation_service.py`**

```python
# backend/modules/budgets/allocation_service.py
import uuid
from datetime import date, datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from modules.households.models import HouseholdBudgetAllocation, BankAccount
from modules.transactions.models import Transaction, TransactionSplit

DEFAULT_ALLOCATION = {"hogar_pct": 50.0, "ahorro_pct": 20.0, "personal_pct": 30.0}
RECOMMENDED_LABEL = "Regla 50/20/30"


def _round5(value: float) -> float:
    """Round to nearest 5."""
    return round(value / 5) * 5


def compute_historical_suggestion(
    monthly_data: list[dict],
) -> dict | None:
    """
    Given a list of {income, hogar_spent, personal_spent} dicts,
    compute the average allocation rounded to nearest 5%.
    Returns None if no months have valid income data.
    """
    valid = [m for m in monthly_data if m.get("income", 0) > 0]
    if not valid:
        return None

    avg_hogar_pct = sum(m["hogar_spent"] / m["income"] * 100 for m in valid) / len(valid)
    avg_personal_pct = sum(m["personal_spent"] / m["income"] * 100 for m in valid) / len(valid)
    avg_ahorro_pct = 100 - avg_hogar_pct - avg_personal_pct

    hogar = _round5(avg_hogar_pct)
    ahorro = max(0.0, _round5(avg_ahorro_pct))
    personal = 100.0 - hogar - ahorro

    return {"hogar_pct": hogar, "ahorro_pct": ahorro, "personal_pct": personal}


async def get_allocation(
    db: AsyncSession, household_id: uuid.UUID, month: date
) -> dict:
    result = await db.execute(
        select(HouseholdBudgetAllocation).where(
            HouseholdBudgetAllocation.household_id == household_id,
            HouseholdBudgetAllocation.month == month,
        )
    )
    alloc = result.scalar_one_or_none()

    allocation_block = (
        {
            "hogar_pct": float(alloc.hogar_pct),
            "ahorro_pct": float(alloc.ahorro_pct),
            "personal_pct": float(alloc.personal_pct),
            "is_default": False,
        }
        if alloc
        else {**DEFAULT_ALLOCATION, "is_default": True}
    )

    # Historical suggestion: look at last 3 months
    monthly_data = []
    for offset in range(1, 4):
        m = month.month - offset
        y = month.year
        while m <= 0:
            m += 12
            y -= 1
        hist_month = date(y, m, 1)
        # Income
        personal_acc_result = await db.execute(
            select(BankAccount.id).where(
                BankAccount.household_id == household_id,
                BankAccount.account_type == "personal",
                BankAccount.is_active.is_(True),
            )
        )
        personal_ids = list(personal_acc_result.scalars().all())

        import calendar
        last_day = calendar.monthrange(y, m)[1]
        first = datetime(y, m, 1, tzinfo=timezone.utc)
        next_m = m + 1 if m < 12 else 1
        next_y = y if m < 12 else y + 1
        first_next = datetime(next_y, next_m, 1, tzinfo=timezone.utc)

        inc_r = await db.execute(
            select(func.sum(Transaction.amount)).where(
                Transaction.bank_account_id.in_(personal_ids),
                Transaction.transaction_type == "income",
                Transaction.transaction_date >= first,
                Transaction.transaction_date < first_next,
            )
        )
        income = float(inc_r.scalar() or 0)

        hogar_r = await db.execute(
            select(func.sum(Transaction.amount))
            .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
            .where(
                Transaction.household_id == household_id,
                Transaction.transaction_type == "expense",
                TransactionSplit.split_type == "shared",
                Transaction.transaction_date >= first,
                Transaction.transaction_date < first_next,
            )
        )
        hogar_spent = float(hogar_r.scalar() or 0)

        personal_r = await db.execute(
            select(func.sum(Transaction.amount))
            .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
            .where(
                Transaction.bank_account_id.in_(personal_ids),
                Transaction.transaction_type == "expense",
                TransactionSplit.split_type == "personal",
                Transaction.transaction_date >= first,
                Transaction.transaction_date < first_next,
            )
        )
        personal_spent = float(personal_r.scalar() or 0)

        monthly_data.append({"income": income, "hogar_spent": hogar_spent, "personal_spent": personal_spent})

    historical = compute_historical_suggestion(monthly_data)

    return {
        "month": month.isoformat(),
        "allocation": allocation_block,
        "suggestions": {
            "historical": historical,
            "recommended": {**DEFAULT_ALLOCATION, "label": RECOMMENDED_LABEL},
        },
    }


async def upsert_allocation(
    db: AsyncSession,
    household_id: uuid.UUID,
    month: date,
    hogar_pct: float,
    ahorro_pct: float,
    personal_pct: float,
) -> dict:
    result = await db.execute(
        select(HouseholdBudgetAllocation).where(
            HouseholdBudgetAllocation.household_id == household_id,
            HouseholdBudgetAllocation.month == month,
        )
    )
    alloc = result.scalar_one_or_none()
    if alloc:
        alloc.hogar_pct = hogar_pct
        alloc.ahorro_pct = ahorro_pct
        alloc.personal_pct = personal_pct
    else:
        alloc = HouseholdBudgetAllocation(
            household_id=household_id,
            month=month,
            hogar_pct=hogar_pct,
            ahorro_pct=ahorro_pct,
            personal_pct=personal_pct,
        )
        db.add(alloc)
    await db.commit()
    return {"hogar_pct": hogar_pct, "ahorro_pct": ahorro_pct, "personal_pct": personal_pct, "is_default": False}
```

- [ ] **Step 2C.4: Run allocation tests — confirm they pass**

```bash
cd backend && python3 -m pytest tests/test_budget_allocation_service.py -v
```

Expected: All tests PASS

- [ ] **Step 2C.5: Run all backend tests**

```bash
cd backend && python3 -m pytest tests/ -v 2>&1 | tail -20
```

Expected: All tests PASS

- [ ] **Step 2C.6: Commit**

```bash
git add backend/modules/budgets/allocation_service.py \
        backend/tests/test_budget_allocation_service.py
git commit -m "feat(budgets): allocation service with 50/20/30 suggestions"
```

---

## Phase 2D — Task 2D: Schemas + Router (Sequential After 2A/2B/2C)

> **Sequential — run after 2A, 2B, 2C are all complete. This is the only task that touches `schemas.py` and `router.py` to avoid parallel write conflicts.**

**Files:**
- Modify: `backend/modules/budgets/schemas.py`
- Modify: `backend/modules/budgets/router.py`

- [ ] **Step 2D.1: Add all new Pydantic schemas to `schemas.py`**

Add `from pydantic import model_validator` to the imports at the top of the file, then append:

```python
# ── Personal budget schemas ──

class PacePoint(BaseModel):
    day: int
    cumulative_spent: float

class PaceBlock(BaseModel):
    spendable_budget: float
    daily_points: list[PacePoint]
    today_day: int
    days_in_month: int
    pace_at_today: float
    actual_at_today: float
    delta: float
    on_track: bool

class BreakdownBlock(BaseModel):
    household: float
    personal: float

class PersonalBlock(BaseModel):
    ceiling: float
    ceiling_clamped: bool
    spent: float
    breakdown: BreakdownBlock
    available: float
    percent_used: float | None

class HouseholdBlock(BaseModel):
    deposited: float | None
    spent: float
    available: float | None
    percent_used: float | None

class PersonalBudgetResponse(BaseModel):
    mode: str  # 'single' | 'waterfall'
    month: str
    income: float
    personal: PersonalBlock
    pace: PaceBlock
    household: HouseholdBlock | None = None

# ── Allocation schemas ──

class AllocationBlock(BaseModel):
    hogar_pct: float
    ahorro_pct: float
    personal_pct: float
    is_default: bool

class AllocationSuggestion(BaseModel):
    hogar_pct: float
    ahorro_pct: float
    personal_pct: float
    label: str | None = None

class AllocationSuggestions(BaseModel):
    historical: AllocationSuggestion | None
    recommended: AllocationSuggestion

class AllocationResponse(BaseModel):
    month: str
    allocation: AllocationBlock
    suggestions: AllocationSuggestions

class SetAllocationRequest(BaseModel):
    month: date
    hogar_pct: float
    ahorro_pct: float
    personal_pct: float

    @model_validator(mode="after")
    def check_sum(self) -> "SetAllocationRequest":
        total = self.hogar_pct + self.ahorro_pct + self.personal_pct
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"Percentages must sum to 100, got {total}")
        return self
```

- [ ] **Step 2D.2: Add all new endpoints to `router.py`**

Append to `backend/modules/budgets/router.py`:

```python
from modules.budgets.personal_service import get_personal_budget
from modules.budgets.allocation_service import get_allocation, upsert_allocation
from modules.budgets.schemas import (
    PersonalBudgetResponse,
    AllocationResponse,
    AllocationBlock,
    SetAllocationRequest,
)


@router.get("/personal/{household_id}", response_model=PersonalBudgetResponse)
async def personal_budget(
    household_id: uuid.UUID,
    month: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    if not month:
        today = date.today()
        month = date(today.year, today.month, 1)
    else:
        month = date(month.year, month.month, 1)
    return await get_personal_budget(db, household_id, current_user.id, month)


@router.get("/allocation/{household_id}", response_model=AllocationResponse)
async def get_budget_allocation(
    household_id: uuid.UUID,
    month: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    if not month:
        today = date.today()
        month = date(today.year, today.month, 1)
    else:
        month = date(month.year, month.month, 1)
    return await get_allocation(db, household_id, month)


@router.post("/allocation/{household_id}", response_model=AllocationBlock)
async def set_budget_allocation(
    household_id: uuid.UUID,
    body: SetAllocationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    month = date(body.month.year, body.month.month, 1)
    return await upsert_allocation(
        db, household_id, month, body.hogar_pct, body.ahorro_pct, body.personal_pct
    )
```

- [ ] **Step 2D.3: Run full backend test suite**

```bash
cd backend && python3 -m pytest tests/ -v 2>&1 | tail -20
```

Expected: All tests PASS

- [ ] **Step 2D.4: Commit**

```bash
git add backend/modules/budgets/schemas.py backend/modules/budgets/router.py
git commit -m "feat(budgets): schemas + router for personal budget + allocation endpoints"
```

---

## Verification Checkpoint 1 — Backend Verifier Agent

> **Dispatch this agent after Task 2D is complete (2A, 2B, 2C, 2D all done).**
> The agent reads the spec and plan, runs all tests, hits the new endpoints, and reports issues.

**Agent prompt to use:**

```
You are a backend verifier for the Luka personal finance app (FastAPI + PostgreSQL).

Your job: verify that the budgeting waterfall feature backend is correctly implemented.

Spec: docs/superpowers/specs/2026-03-20-budgeting-personal-household-design.md
Plan: docs/superpowers/plans/2026-03-20-budgeting-personal-household-waterfall.md

Run these checks and report PASS or FAIL for each:

1. Run all backend tests:
   cd backend && python3 -m pytest tests/ -v
   Expected: All pass, 0 failures.

2. Check TypeScript compilation is unaffected (no backend TS, skip).

3. Check migration file exists and has correct revision:
   cat backend/alembic/versions/011_transaction_type_budget_allocations.py | grep revision

4. Check Transaction model has the new fields:
   grep -n "transaction_type\|transfer_to_account_id" backend/modules/transactions/models.py

5. Check HouseholdBudgetAllocation model exists:
   grep -n "HouseholdBudgetAllocation" backend/modules/households/models.py

6. Check FintocClient no longer has debit-only filter:
   grep "amount < 0" backend/modules/fintoc/client.py
   Expected: No match (filter removed).

7. Check classifier module exists and exports classify_movement:
   grep "def classify_movement" backend/modules/fintoc/classifier.py

8. Check new endpoints registered:
   grep -n "personal\|allocation" backend/modules/budgets/router.py

9. Check reconciler passes transaction_type:
   grep "transaction_type" backend/modules/fintoc/reconciler.py

10. Check import_fintoc_history gates split_map on expense:
    grep -A5 "cls_result.classification == MovementClassification.EXPENSE" backend/jobs/tasks.py

11. Check transfer_to_account_id is written (not always NULL):
    grep "transfer_to_account_id" backend/jobs/tasks.py
    Expected: at least one assignment (transfer_to_account_id=transfer_to)

Report: list of checks with PASS/FAIL and any error output. If any FAIL, describe what needs fixing.
```

> If verifier reports failures, fix them before proceeding to Phase 3.

---

## Phase 3A — Task 3A: Frontend Types + API Methods + Hooks

> **Sequential — must complete before 3B/3C/3D.**

**Files:**
- Modify: `frontend/app/lib/api.ts`
- Modify: `frontend/app/lib/hooks/useBudget.ts`

- [ ] **Step 3A.1: Add new TypeScript interfaces to `api.ts`**

Add after the existing `BudgetStatus` interface:

```typescript
// Pace chart
export interface PacePoint {
  day: number;
  cumulative_spent: number;
}

export interface PaceBlock {
  spendable_budget: number;
  daily_points: PacePoint[];
  today_day: number;
  days_in_month: number;
  pace_at_today: number;
  actual_at_today: number;
  delta: number;
  on_track: boolean;
}

// Waterfall budget
export interface PersonalBreakdown {
  household: number;
  personal: number;
}

export interface PersonalBlock {
  ceiling: number;
  ceiling_clamped: boolean;
  spent: number;
  breakdown: PersonalBreakdown;
  available: number;
  percent_used: number | null;
}

export interface HouseholdBlock {
  deposited: number | null;
  spent: number;
  available: number | null;
  percent_used: number | null;
}

export interface PersonalBudgetResponse {
  mode: "single" | "waterfall";
  month: string;
  income: number;
  personal: PersonalBlock;
  pace: PaceBlock;
  household?: HouseholdBlock;
}

// Allocation
export interface AllocationBlock {
  hogar_pct: number;
  ahorro_pct: number;
  personal_pct: number;
  is_default: boolean;
}

export interface AllocationSuggestion {
  hogar_pct: number;
  ahorro_pct: number;
  personal_pct: number;
  label?: string;
}

export interface AllocationResponse {
  month: string;
  allocation: AllocationBlock;
  suggestions: {
    historical: AllocationSuggestion | null;
    recommended: AllocationSuggestion;
  };
}

export interface SetAllocationPayload {
  month: string;       // YYYY-MM-DD
  hogar_pct: number;
  ahorro_pct: number;
  personal_pct: number;
}
```

- [ ] **Step 3A.2: Add new API methods to `api.ts`**

Inside the `api` object, add:

```typescript
getPersonalBudget: (householdId: string, month?: string) =>
  apiFetch<PersonalBudgetResponse>(
    `/budgets/personal/${householdId}${month ? `?month=${month}` : ""}`
  ),

getAllocation: (householdId: string, month?: string) =>
  apiFetch<AllocationResponse>(
    `/budgets/allocation/${householdId}${month ? `?month=${month}` : ""}`
  ),

setAllocation: (householdId: string, payload: SetAllocationPayload) =>
  apiFetch<AllocationBlock>(`/budgets/allocation/${householdId}`, {
    method: "POST",
    body: JSON.stringify(payload),
  }),
```

- [ ] **Step 3A.3: Add new hooks to `useBudget.ts`**

```typescript
export function usePersonalBudget(month?: string) {
  const householdId = useLukaStore((s) => s.householdId);
  return useQuery({
    queryKey: ["personalBudget", householdId, month],
    queryFn: () => api.getPersonalBudget(householdId!, month),
    enabled: !!householdId,
  });
}

export function useAllocation(month?: string) {
  const householdId = useLukaStore((s) => s.householdId);
  return useQuery({
    queryKey: ["allocation", householdId, month],
    queryFn: () => api.getAllocation(householdId!, month),
    enabled: !!householdId,
  });
}

export function useSaveAllocation() {
  const householdId = useLukaStore((s) => s.householdId);
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: import("@/app/lib/api").SetAllocationPayload) => {
      if (!householdId) throw new Error("No household");
      return api.setAllocation(householdId, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["allocation"] });
      queryClient.invalidateQueries({ queryKey: ["personalBudget"] });
    },
  });
}
```

- [ ] **Step 3A.4: Check TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: No errors

- [ ] **Step 3A.5: Commit**

```bash
git add frontend/app/lib/api.ts frontend/app/lib/hooks/useBudget.ts
git commit -m "feat(frontend): budget waterfall types, API methods, and hooks"
```

---

## Phase 3B — Task 3B: PaceChart Component

> **Parallel with 3C and 3D. Requires 3A complete.**

**Files:**
- Create: `frontend/app/(dashboard)/components/PaceChart.tsx`

- [ ] **Step 3B.1: Implement `PaceChart.tsx`**

```tsx
// frontend/app/(dashboard)/components/PaceChart.tsx
"use client";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  Dot,
} from "recharts";
import type { PaceBlock } from "@/app/lib/api";

interface Props {
  pace: PaceBlock;
}

function formatCLP(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `$${Math.round(n / 1_000)}K`;
  return `$${Math.round(n)}`;
}

export default function PaceChart({ pace }: Props) {
  const {
    daily_points,
    today_day,
    days_in_month,
    spendable_budget,
    delta,
    on_track,
  } = pace;

  // Build chart data: actual points + dashed pace line for full month
  const chartData = Array.from({ length: days_in_month }, (_, i) => {
    const day = i + 1;
    const actual = daily_points.find((p) => p.day === day);
    const paceValue = Math.round((spendable_budget * day) / days_in_month);
    return {
      day,
      actual: actual ? actual.cumulative_spent : day <= today_day ? (daily_points.at(-1)?.cumulative_spent ?? 0) : null,
      pace: paceValue,
    };
  });

  const calloutColor = on_track ? "text-luka-success" : "text-luka-danger";
  const calloutText = on_track
    ? `${formatCLP(Math.abs(delta))} bajo el ritmo`
    : `${formatCLP(Math.abs(delta))} sobre el ritmo`;

  if (spendable_budget === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-sm text-luka-muted">
        Conecta tu banco para ver el gráfico de ritmo
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <div className={`text-sm font-semibold text-right ${calloutColor}`}>
        {calloutText}
      </div>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <XAxis
            dataKey="day"
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11, fill: "#64748B" }}
            ticks={[1, 5, 10, 15, 20, 25, days_in_month]}
          />
          <YAxis hide />
          <Tooltip
            formatter={(val: number) => formatCLP(val)}
            labelFormatter={(d) => `Día ${d}`}
            contentStyle={{ fontSize: 12, borderRadius: 8 }}
          />
          {/* Dashed pace line */}
          <Line
            type="linear"
            dataKey="pace"
            stroke="#CBD5E1"
            strokeDasharray="4 4"
            dot={false}
            strokeWidth={1.5}
          />
          {/* Actual spending line — color by on_track */}
          <Line
            type="monotone"
            dataKey="actual"
            stroke={on_track ? "#10B981" : "#EF4444"}
            dot={false}
            strokeWidth={2.5}
            connectNulls={false}
          />
          {/* Today marker */}
          <ReferenceLine x={today_day} stroke="#94A3B8" strokeDasharray="2 2" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 3B.2: Check TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep PaceChart
```

Expected: No errors

- [ ] **Step 3B.3: Commit**

```bash
git add frontend/app/(dashboard)/components/PaceChart.tsx
git commit -m "feat(frontend): PaceChart component (cumulative spend vs pace line)"
```

---

## Phase 3C — Task 3C: AllocationCard Component

> **Parallel with 3B and 3D. Requires 3A complete.**

**Files:**
- Create: `frontend/app/(dashboard)/components/AllocationCard.tsx`

- [ ] **Step 3C.1: Implement `AllocationCard.tsx`**

```tsx
// frontend/app/(dashboard)/components/AllocationCard.tsx
"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { AllocationResponse, SetAllocationPayload } from "@/app/lib/api";

interface Props {
  allocation: AllocationResponse;
  income: number;
  month: string; // YYYY-MM-DD
  onSave: (payload: SetAllocationPayload) => void;
  isSaving: boolean;
}

function CLP(n: number) {
  return `$${Math.round(n).toLocaleString("es-CL")}`;
}

export default function AllocationCard({ allocation, income, month, onSave, isSaving }: Props) {
  const [hogar, setHogar] = useState(allocation.allocation.hogar_pct);
  const [ahorro, setAhorro] = useState(allocation.allocation.ahorro_pct);
  const personal = Math.max(0, 100 - hogar - ahorro);
  const [isEditing, setIsEditing] = useState(allocation.allocation.is_default);

  function applySuggestion(s: { hogar_pct: number; ahorro_pct: number; personal_pct: number }) {
    setHogar(s.hogar_pct);
    setAhorro(s.ahorro_pct);
  }

  function handleSave() {
    onSave({ month, hogar_pct: hogar, ahorro_pct: ahorro, personal_pct: personal });
    setIsEditing(false);
  }

  if (!isEditing) {
    return (
      <Card className="bg-white">
        <CardHeader className="pb-2 flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-semibold text-luka-dark">Tu presupuesto</CardTitle>
          <button
            onClick={() => setIsEditing(true)}
            className="text-xs text-luka-primary hover:underline"
          >
            Editar
          </button>
        </CardHeader>
        <CardContent>
          <div className="flex justify-between text-sm text-luka-muted">
            <span>Hogar <span className="text-luka-dark font-medium">{hogar}%</span></span>
            <span>Ahorro <span className="text-luka-dark font-medium">{ahorro}%</span></span>
            <span>Personal <span className="text-luka-dark font-medium">{personal}%</span></span>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-white">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-luka-dark">Tu presupuesto</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Suggestion pills */}
        <div className="flex gap-2 flex-wrap">
          {allocation.suggestions.historical && (
            <button
              onClick={() => applySuggestion(allocation.suggestions.historical!)}
              className="text-xs px-3 py-1 rounded-full bg-luka-light text-luka-primary border border-luka-primary"
            >
              Según tu historial
            </button>
          )}
          <button
            onClick={() => applySuggestion(allocation.suggestions.recommended)}
            className="text-xs px-3 py-1 rounded-full bg-luka-light text-luka-muted border border-gray-200"
          >
            {allocation.suggestions.recommended.label ?? "Regla 50/20/30"}
          </button>
        </div>

        {/* Hogar slider */}
        <div className="space-y-1">
          <div className="flex justify-between text-sm">
            <span className="text-luka-muted">Hogar</span>
            <span className="text-luka-dark font-medium">
              {hogar}% — {income > 0 ? CLP(income * hogar / 100) : "—"}
            </span>
          </div>
          <input
            type="range" min={0} max={100 - ahorro} step={5}
            value={hogar}
            onChange={(e) => setHogar(Number(e.target.value))}
            className="w-full accent-luka-sky"
          />
        </div>

        {/* Ahorro slider */}
        <div className="space-y-1">
          <div className="flex justify-between text-sm">
            <span className="text-luka-muted">Ahorro</span>
            <span className="text-luka-dark font-medium">
              {ahorro}% — {income > 0 ? CLP(income * ahorro / 100) : "—"}
            </span>
          </div>
          <input
            type="range" min={0} max={100 - hogar} step={5}
            value={ahorro}
            onChange={(e) => setAhorro(Number(e.target.value))}
            className="w-full accent-luka-primary"
          />
        </div>

        {/* Personal (read-only) */}
        <div className="flex justify-between text-sm">
          <span className="text-luka-muted">Personal (resto)</span>
          <span className="text-luka-dark font-medium">
            {personal}% — {income > 0 ? CLP(income * personal / 100) : "—"}
          </span>
        </div>

        {personal < 0 && (
          <p className="text-xs text-luka-danger">
            Hogar + Ahorro supera el 100%. Ajusta los valores.
          </p>
        )}
        <Button
          onClick={handleSave}
          disabled={isSaving || personal < 0}
          className="w-full bg-luka-primary text-white"
        >
          {isSaving ? "Guardando..." : "Guardar"}
        </Button>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 3C.2: Check TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep AllocationCard
```

Expected: No errors

- [ ] **Step 3C.3: Commit**

```bash
git add frontend/app/(dashboard)/components/AllocationCard.tsx
git commit -m "feat(frontend): AllocationCard with sliders and suggestion pills"
```

---

## Phase 3D — Task 3D: WaterfallCards Component

> **Parallel with 3B and 3C. Requires 3A complete.**

**Files:**
- Create: `frontend/app/(dashboard)/components/WaterfallCards.tsx`

- [ ] **Step 3D.1: Implement `WaterfallCards.tsx`**

```tsx
// frontend/app/(dashboard)/components/WaterfallCards.tsx
"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { PersonalBudgetResponse } from "@/app/lib/api";

interface Props {
  budget: PersonalBudgetResponse;
}

function CLP(n: number) {
  return `$${Math.round(n).toLocaleString("es-CL")}`;
}

function ProgressBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="w-full bg-luka-light rounded-full h-2">
      <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function barColor(pct: number | null): string {
  if (!pct) return "bg-luka-primary";
  if (pct > 90) return "bg-luka-danger";
  if (pct > 70) return "bg-yellow-400";
  return "bg-luka-primary";
}

export default function WaterfallCards({ budget }: Props) {
  const { household, personal, mode } = budget;

  return (
    <div className="space-y-3">
      {/* Household card — waterfall mode only */}
      {mode === "waterfall" && household && (
        <Card className="bg-white">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-luka-dark">Hogar</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {household.deposited !== null ? (
              <>
                <div className="flex justify-between text-sm">
                  <span className="text-luka-muted">Depositado</span>
                  <span className="text-luka-dark font-medium">{CLP(household.deposited)}</span>
                </div>
                <ProgressBar
                  value={household.spent}
                  max={household.deposited}
                  color={barColor(household.percent_used)}
                />
                <div className="flex justify-between text-xs text-luka-muted">
                  <span>Gastado: {CLP(household.spent)} ({household.percent_used ?? 0}%)</span>
                  <span className={household.available !== null && household.available >= 0 ? "text-luka-success font-semibold" : "text-luka-danger font-semibold"}>
                    {household.available !== null
                      ? household.available >= 0
                        ? `Disponible: ${CLP(household.available)}`
                        : `Excedido: ${CLP(Math.abs(household.available))}`
                      : null}
                  </span>
                </div>
              </>
            ) : (
              <p className="text-sm text-luka-muted">
                Gastos compartidos: <span className="text-luka-dark font-medium">{CLP(household.spent)}</span>
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Personal card */}
      <Card className="bg-white">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold text-luka-dark">Personal</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex justify-between text-sm">
            <span className="text-luka-muted">Techo</span>
            <span className={personal.ceiling_clamped ? "text-luka-danger font-medium" : "text-luka-dark font-medium"}>
              {personal.ceiling_clamped ? "Transferencias superan ingresos" : CLP(personal.ceiling)}
            </span>
          </div>

          {!personal.ceiling_clamped && personal.ceiling > 0 && (
            <div className="space-y-2">
              {/* Hogar-tagged bar */}
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-luka-muted">
                  <span>Hogar</span>
                  <span>{CLP(personal.breakdown.household)}</span>
                </div>
                <ProgressBar
                  value={personal.breakdown.household}
                  max={personal.ceiling}
                  color="bg-luka-sky"
                />
              </div>
              {/* Personal bar */}
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-luka-muted">
                  <span>Personal</span>
                  <span>{CLP(personal.breakdown.personal)}</span>
                </div>
                <ProgressBar
                  value={personal.breakdown.personal}
                  max={personal.ceiling}
                  color="bg-luka-primary"
                />
              </div>
            </div>
          )}

          <div className={`text-xs font-semibold text-right ${personal.available >= 0 ? "text-luka-success" : "text-luka-danger"}`}>
            {personal.available >= 0
              ? `Disponible: ${CLP(personal.available)}`
              : `Excedido: ${CLP(Math.abs(personal.available))}`}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 3D.2: Check TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep WaterfallCards
```

Expected: No errors

- [ ] **Step 3D.3: Commit**

```bash
git add frontend/app/(dashboard)/components/WaterfallCards.tsx
git commit -m "feat(frontend): WaterfallCards — household + personal progress bars"
```

---

## Phase 3E — Task 3E: Budgets Page (Wire Everything)

> **Sequential — requires 3B, 3C, 3D complete.**

**Files:**
- Modify: `frontend/app/(dashboard)/budgets/page.tsx`

- [ ] **Step 3E.1: Rewrite `budgets/page.tsx`**

```tsx
// frontend/app/(dashboard)/budgets/page.tsx
"use client";
import { useState } from "react";
import { usePersonalBudget, useAllocation, useSaveAllocation } from "@/app/lib/hooks/useBudget";
import PaceChart from "@/app/(dashboard)/components/PaceChart";
import AllocationCard from "@/app/(dashboard)/components/AllocationCard";
import WaterfallCards from "@/app/(dashboard)/components/WaterfallCards";
import { useLukaStore } from "@/app/lib/store";

function CLP(n: number) {
  return `$${Math.round(n).toLocaleString("es-CL")}`;
}

function getMonthParam(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-01`;
}

export default function BudgetsPage() {
  const [selectedMonth, setSelectedMonth] = useState<Date>(
    new Date(new Date().getFullYear(), new Date().getMonth(), 1)
  );
  const monthParam = getMonthParam(selectedMonth);

  const { data: budget, isLoading: budgetLoading } = usePersonalBudget(monthParam);
  const { data: allocation, isLoading: allocLoading } = useAllocation(monthParam);
  const { mutate: saveAllocation, isPending: isSaving } = useSaveAllocation();

  function prevMonth() {
    setSelectedMonth(new Date(selectedMonth.getFullYear(), selectedMonth.getMonth() - 1, 1));
  }
  function nextMonth() {
    const next = new Date(selectedMonth.getFullYear(), selectedMonth.getMonth() + 1, 1);
    if (next <= new Date()) setSelectedMonth(next);
  }
  const isCurrentMonth =
    selectedMonth.getFullYear() === new Date().getFullYear() &&
    selectedMonth.getMonth() === new Date().getMonth();

  if (budgetLoading || allocLoading) {
    return <p className="text-luka-muted">Cargando...</p>;
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-luka-dark tracking-tight">Presupuesto</h2>
        <p className="text-sm text-luka-muted mt-0.5">Control de ingresos y gastos</p>
      </div>

      {/* Month selector */}
      <div className="flex items-center gap-3 text-sm">
        <button onClick={prevMonth} className="text-luka-muted hover:text-luka-dark">‹</button>
        <span className="font-medium text-luka-dark capitalize">
          {selectedMonth.toLocaleDateString("es-CL", { month: "long", year: "numeric" })}
        </span>
        <button
          onClick={nextMonth}
          disabled={isCurrentMonth}
          className="text-luka-muted hover:text-luka-dark disabled:opacity-30"
        >
          ›
        </button>
      </div>

      {/* Income header */}
      <div className="text-sm text-luka-muted">
        {budget && budget.income > 0 ? (
          <span>
            Ingresos: <span className="text-luka-dark font-semibold">{CLP(budget.income)}</span>
          </span>
        ) : (
          <span className="text-gray-400">Conecta tu banco para ver tus ingresos</span>
        )}
      </div>

      {/* Pace chart */}
      {budget && budget.pace && (
        <div className="bg-white rounded-xl border border-gray-100 p-4">
          <p className="text-xs font-semibold text-luka-muted uppercase tracking-wide mb-3">
            Ritmo de gastos
          </p>
          <PaceChart pace={budget.pace} />
        </div>
      )}

      {/* Allocation card */}
      {allocation && budget && (
        <AllocationCard
          allocation={allocation}
          income={budget.income}
          month={monthParam}
          onSave={saveAllocation}
          isSaving={isSaving}
        />
      )}

      {/* Waterfall cards */}
      {budget && <WaterfallCards budget={budget} />}
    </div>
  );
}
```

- [ ] **Step 3E.2: Check TypeScript compiles — full project**

```bash
cd frontend && npx tsc --noEmit 2>&1
```

Expected: 0 errors

- [ ] **Step 3E.3: Check Next.js builds without errors**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Expected: `✓ Compiled successfully`

- [ ] **Step 3E.4: Commit**

```bash
git add frontend/app/(dashboard)/budgets/page.tsx
git commit -m "feat(frontend): budgets page — waterfall + pace chart + allocation editor"
```

---

## Verification Checkpoint 2 — Frontend Verifier Agent

> **Dispatch after Task 3E is complete.**

**Agent prompt to use:**

```
You are a frontend verifier for the Luka personal finance app (Next.js 16 + TypeScript + Recharts).

Your job: verify the budgeting waterfall feature frontend is correctly implemented.

Spec: docs/superpowers/specs/2026-03-20-budgeting-personal-household-design.md
Plan: docs/superpowers/plans/2026-03-20-budgeting-personal-household-waterfall.md

Run these checks and report PASS or FAIL for each:

1. TypeScript compilation — no errors:
   cd frontend && npx tsc --noEmit
   Expected: exit code 0, 0 errors

2. Next.js build — no errors:
   cd frontend && npm run build
   Expected: "Compiled successfully"

3. Check PaceChart renders the dashed pace line and solid actual line:
   grep -n "strokeDasharray\|dataKey.*pace\|dataKey.*actual" frontend/app/(dashboard)/components/PaceChart.tsx

4. Check AllocationCard has 3 sliders and a save button:
   grep -c "type=\"range\"" frontend/app/(dashboard)/components/AllocationCard.tsx
   Expected: 2 (Hogar + Ahorro; Personal is read-only)

5. Check WaterfallCards handles null deposited (couple-no-joint):
   grep -n "deposited !== null\|deposited === null" frontend/app/(dashboard)/components/WaterfallCards.tsx

6. Check budgets page uses all 3 new hooks:
   grep -n "usePersonalBudget\|useAllocation\|useSaveAllocation" frontend/app/(dashboard)/budgets/page.tsx

7. Check api.ts has the 3 new API methods:
   grep -n "getPersonalBudget\|getAllocation\|setAllocation" frontend/app/lib/api.ts

8. Check useBudget.ts exports the 3 new hooks:
   grep -n "export function usePersonalBudget\|export function useAllocation\|export function useSaveAllocation" frontend/app/lib/hooks/useBudget.ts

9. Check old BudgetStatus/useBudgetStatus still exists (existing endpoint not removed):
   grep -n "BudgetStatus\|useBudgetStatus" frontend/app/lib/hooks/useBudget.ts

Report: list of checks with PASS/FAIL. If any FAIL, describe what needs fixing.
```

> If verifier reports failures, fix them before Phase 4.

---

## Phase 4 — Task 4: Final Integration Commit

> **Sequential — run after both verification checkpoints pass.**

- [ ] **Step 4.1: Run full backend test suite one final time**

```bash
cd backend && python3 -m pytest tests/ -v
```

Expected: All pass

- [ ] **Step 4.2: Run full frontend build one final time**

```bash
cd frontend && npm run build
```

Expected: `✓ Compiled successfully`

- [ ] **Step 4.3: Final commit**

```bash
git add -A
git commit -m "feat(budgets): personal + household waterfall, pace chart, allocation editor

- Add transaction_type (expense/income/transfer) + household_budget_allocations table (migration 011)
- Fintoc classifier detects inflows/transfers via counterparty ID or keyword+symmetry fallback
- run_fintoc_sync + import_fintoc_history use classifier; split_map gated on expense only
- New endpoints: GET/POST /budgets/personal + GET/POST /budgets/allocation
- Frontend: PaceChart (Recharts), AllocationCard (sliders + suggestion pills), WaterfallCards
- Budgets page fully rewritten with month selector, income header, pace chart, allocation, waterfall"
```

- [ ] **Step 4.4: Note for production deployment**

> ⚠️ **Deploy sequencing:** Migration 011 and the updated backend code must be deployed in the same Railway deploy. Run `python3 -m alembic upgrade head` on production before the new endpoints are live. The migration adds `DEFAULT 'expense'` on `transaction_type` — safe for existing rows.

---

## Summary: Parallelism Map for Agent Dispatch

| Wave | Tasks | Can dispatch simultaneously? |
|------|-------|------------------------------|
| 1 | Task 1 (Migration + Models) | No — run alone |
| 2 | Tasks 2A + 2B + 2C | Yes — dispatch all 3 in parallel (service files only) |
| 3 | Task 2D (Schemas + Router) | No — run after wave 2, touches shared files |
| — | Verification Checkpoint 1 | Run after Task 2D |
| 4 | Task 3A (Types + Hooks) | No — run alone (frontend foundation) |
| 5 | Tasks 3B + 3C + 3D | Yes — dispatch all 3 in parallel |
| 6 | Task 3E (Budgets page) | No — run after wave 5 |
| — | Verification Checkpoint 2 | Run after 3E |
| 7 | Task 4 (Final commit) | No — run last |
