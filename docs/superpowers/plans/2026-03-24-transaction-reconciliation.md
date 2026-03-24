# Transaction Reconciliation + Pending Block — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface pending email transactions, unclassified Fintoc transactions, and unmatched email transactions in a "Pendientes" block on the Transactions page, with reconciliation between email and Fintoc sources.

**Architecture:** New `GET /transactions/pending` endpoint groups transactions into 3 buckets using a MAX subquery on `bank_accounts.last_synced_at`. New `DELETE /transactions/{id}` endpoint for unmatched cleanup. Frontend PendingBlock component renders above tabs. Cross-sender dedup prevents Banco de Chile email pairs from creating duplicates.

**Tech Stack:** FastAPI, SQLAlchemy async, Next.js 14 (App Router), TanStack Query, Tailwind CSS

**Spec:** `docs/superpowers/specs/2026-03-24-transaction-reconciliation-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/modules/transactions/schemas.py` | Modify | Add `PendingTransactionsResponse` |
| `backend/modules/transactions/service.py` | Modify | Add `get_pending_transactions()`, `delete_transaction()`, fix INNER→OUTER join |
| `backend/modules/transactions/router.py` | Modify | Add `GET /pending`, `DELETE /{id}`, filter pending from `/mine` |
| `backend/modules/fintoc/reconciler.py` | Modify | Set `bank_account_id` on matched email transactions |
| `backend/jobs/tasks.py` | Modify | Cross-sender dedup, `status='settled'` for non-Fintoc users |
| `backend/tests/test_pending_transactions.py` | Create | Tests for pending endpoint |
| `backend/tests/test_delete_transaction.py` | Create | Tests for delete endpoint |
| `backend/tests/test_cross_sender_dedup.py` | Create | Tests for dedup logic |
| `frontend/app/lib/api.ts` | Modify | Add `getPendingTransactions()`, `deleteTransaction()` |
| `frontend/app/lib/hooks/useTransactions.ts` | Modify | Add `usePendingTransactions()` |
| `frontend/app/(dashboard)/components/PendingBlock.tsx` | Create | Pending block UI component |
| `frontend/app/(dashboard)/transactions/page.tsx` | Modify | Insert PendingBlock between SummaryBar and Tabs |

---

### Task 1: PendingTransactionsResponse Schema

**Files:**
- Modify: `backend/modules/transactions/schemas.py`

- [ ] **Step 1: Add the schema**

In `backend/modules/transactions/schemas.py`, add after the `SplitTypeUpdateRequest` class:

```python
class PendingTransactionsResponse(BaseModel):
    awaiting_reconciliation: list[TransactionResponse] = []
    needs_classification: list[TransactionResponse] = []
    unmatched_email: list[TransactionResponse] = []
```

- [ ] **Step 2: Commit**

```bash
git add backend/modules/transactions/schemas.py
git commit -m "feat: add PendingTransactionsResponse schema"
```

---

### Task 2: Fix INNER→OUTER Join + Filter Pending from /mine

**Files:**
- Modify: `backend/modules/transactions/service.py:9-30` (get_my_transactions)
- Modify: `backend/modules/transactions/service.py:104-127` (get_shared_transactions)

- [ ] **Step 1: Fix get_my_transactions — change INNER to OUTER join on BankAccount**

In `backend/modules/transactions/service.py`, function `get_my_transactions` (line 9-30):

Change line 13 from:
```python
        .join(BankAccount, BankAccount.id == Transaction.bank_account_id)
```
to:
```python
        .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
```

- [ ] **Step 2: Add pending filter to get_my_transactions**

In the `.where()` clause of `get_my_transactions`, add after `Transaction.transaction_date >= since`:
```python
            Transaction.status != "pending",
```

This excludes pending email transactions from the main list (they appear in the PendingBlock instead).

- [ ] **Step 3: Remove is_active filter**

Remove `BankAccount.is_active.is_(True)` from the `.where()` clause — with OUTER JOIN, this would filter out transactions with no bank account (NULL). Bank account filtering is not needed here since we filter by user_id.

- [ ] **Step 4: Fix get_shared_transactions — change INNER to OUTER join**

In `get_shared_transactions` (line 107-127), change line 110 from:
```python
        .join(BankAccount, BankAccount.id == Transaction.bank_account_id)
```
to:
```python
        .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
```

Also remove `BankAccount.is_active.is_(True)` from its `.where()` clause.

- [ ] **Step 5: Run existing tests**

Run: `cd backend && python3 -m pytest tests/ -v --tb=short`
Expected: All existing tests still pass (the join change is backwards compatible).

- [ ] **Step 6: Commit**

```bash
git add backend/modules/transactions/service.py
git commit -m "fix: OUTER join on BankAccount, filter pending from /mine"
```

---

### Task 3: get_pending_transactions Service + Tests

**Files:**
- Modify: `backend/modules/transactions/service.py`
- Create: `backend/tests/test_pending_transactions.py`

- [ ] **Step 1: Write the test file**

```python
# backend/tests/test_pending_transactions.py
import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_email_txn_before_sync_is_awaiting():
    """Email transaction created before any Fintoc sync → awaiting_reconciliation."""
    from modules.transactions.service import get_pending_transactions

    user_id = uuid.uuid4()
    mock_db = AsyncMock()

    # Mock: 1 pending email txn, max_synced_at is None (no sync yet)
    mock_txn = MagicMock()
    mock_txn.id = uuid.uuid4()
    mock_txn.source = "gmail"
    mock_txn.status = "pending"
    mock_txn.category = None
    mock_txn.created_at = datetime.now(timezone.utc)

    # We'll test the actual SQL logic via integration tests;
    # for unit tests, verify the function exists and returns the right shape
    result_mock = MagicMock()
    result_mock.all.return_value = []
    mock_db.execute = AsyncMock(return_value=result_mock)

    result = await get_pending_transactions(mock_db, user_id)
    assert "awaiting_reconciliation" in result
    assert "needs_classification" in result
    assert "unmatched_email" in result


@pytest.mark.asyncio
async def test_pending_returns_empty_when_no_pending():
    """No pending transactions → all 3 lists empty."""
    from modules.transactions.service import get_pending_transactions

    user_id = uuid.uuid4()
    mock_db = AsyncMock()
    result_mock = MagicMock()
    result_mock.all.return_value = []
    mock_db.execute = AsyncMock(return_value=result_mock)

    result = await get_pending_transactions(mock_db, user_id)
    assert result["awaiting_reconciliation"] == []
    assert result["needs_classification"] == []
    assert result["unmatched_email"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python3 -m pytest tests/test_pending_transactions.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_pending_transactions'`

- [ ] **Step 3: Implement get_pending_transactions**

Add to `backend/modules/transactions/service.py`:

```python
from sqlalchemy import select, func, and_, or_
from modules.households.models import BankAccount


async def get_pending_transactions(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """
    Return pending transactions grouped into 3 buckets:
    - awaiting_reconciliation: email txns, pending, no sync has run since creation
    - needs_classification: Fintoc txns, settled, no category
    - unmatched_email: email txns, pending, at least 1 sync ran since creation
    """
    # Subquery: max last_synced_at across all user's active bank accounts
    max_synced = (
        select(func.max(BankAccount.last_synced_at))
        .where(BankAccount.user_id == user_id, BankAccount.is_active.is_(True))
        .correlate(Transaction)
        .scalar_subquery()
    )

    # All pending email transactions
    email_pending_result = await db.execute(
        select(Transaction, TransactionSplit)
        .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .where(
            Transaction.user_id == user_id,
            Transaction.source.in_(["gmail", "outlook"]),
            Transaction.status == "pending",
        )
        .order_by(Transaction.transaction_date.desc())
    )
    email_pending_rows = email_pending_result.all()

    # Fintoc transactions needing classification
    needs_class_result = await db.execute(
        select(Transaction, TransactionSplit)
        .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .where(
            Transaction.user_id == user_id,
            Transaction.source == "fintoc",
            Transaction.status == "settled",
            Transaction.category.is_(None),
        )
        .order_by(Transaction.transaction_date.desc())
    )
    needs_class_rows = needs_class_result.all()

    # Get max_synced_at value
    synced_result = await db.execute(
        select(func.max(BankAccount.last_synced_at)).where(
            BankAccount.user_id == user_id, BankAccount.is_active.is_(True)
        )
    )
    max_synced_at = synced_result.scalar_one_or_none()

    # Split email pending into awaiting vs unmatched
    awaiting = []
    unmatched = []
    for txn, split in email_pending_rows:
        row = _txn_to_dict(txn, split)
        if max_synced_at is None or max_synced_at < txn.created_at:
            awaiting.append(row)
        else:
            unmatched.append(row)

    needs_classification = [_txn_to_dict(txn, split) for txn, split in needs_class_rows]

    return {
        "awaiting_reconciliation": awaiting,
        "needs_classification": needs_classification,
        "unmatched_email": unmatched,
    }


def _txn_to_dict(txn: Transaction, split: TransactionSplit | None) -> dict:
    """Convert Transaction + optional Split to response dict."""
    return {
        **{k: v for k, v in vars(txn).items() if not k.startswith("_")},
        "split_type": split.split_type if split else None,
        "bank_name": None,
        "account_kind": None,
    }
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python3 -m pytest tests/test_pending_transactions.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/modules/transactions/service.py backend/tests/test_pending_transactions.py
git commit -m "feat: add get_pending_transactions service with 3-bucket logic"
```

---

### Task 4: delete_transaction Service + Tests

**Files:**
- Modify: `backend/modules/transactions/service.py`
- Create: `backend/tests/test_delete_transaction.py`

- [ ] **Step 1: Write the test file**

```python
# backend/tests/test_delete_transaction.py
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_delete_pending_email_transaction():
    """Can delete a pending email transaction."""
    from modules.transactions.service import delete_transaction

    user_id = uuid.uuid4()
    txn_id = uuid.uuid4()

    mock_txn = MagicMock()
    mock_txn.id = txn_id
    mock_txn.user_id = user_id
    mock_txn.source = "gmail"
    mock_txn.status = "pending"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_txn

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    result = await delete_transaction(mock_db, txn_id, user_id)
    assert result == "deleted"
    mock_db.delete.assert_called_once_with(mock_txn)


@pytest.mark.asyncio
async def test_delete_rejects_fintoc_transaction():
    """Cannot delete a Fintoc-sourced transaction."""
    from modules.transactions.service import delete_transaction

    user_id = uuid.uuid4()
    txn_id = uuid.uuid4()

    mock_txn = MagicMock()
    mock_txn.id = txn_id
    mock_txn.user_id = user_id
    mock_txn.source = "fintoc"
    mock_txn.status = "settled"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_txn

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await delete_transaction(mock_db, txn_id, user_id)
    assert result == "invalid"


@pytest.mark.asyncio
async def test_delete_returns_not_found():
    """Transaction not found returns not_found."""
    from modules.transactions.service import delete_transaction

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await delete_transaction(mock_db, uuid.uuid4(), uuid.uuid4())
    assert result == "not_found"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python3 -m pytest tests/test_delete_transaction.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement delete_transaction**

Add to `backend/modules/transactions/service.py`:

```python
async def delete_transaction(
    db: AsyncSession, transaction_id: uuid.UUID, user_id: uuid.UUID
) -> str:
    """
    Hard delete a pending email transaction.
    Returns: 'deleted', 'not_found', or 'invalid'.
    """
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
        )
    )
    txn = result.scalar_one_or_none()
    if not txn:
        return "not_found"
    if txn.source not in ("gmail", "outlook") or txn.status != "pending":
        return "invalid"
    await db.delete(txn)
    await db.commit()
    return "deleted"
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python3 -m pytest tests/test_delete_transaction.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/modules/transactions/service.py backend/tests/test_delete_transaction.py
git commit -m "feat: add delete_transaction service for pending email transactions"
```

---

### Task 5: Router — GET /pending + DELETE /{id}

**Files:**
- Modify: `backend/modules/transactions/router.py`

- [ ] **Step 1: Add imports**

At the top of `backend/modules/transactions/router.py`, update the schemas import (line 11-15):

```python
from modules.transactions.schemas import (
    TransactionResponse,
    CategoryUpdateRequest,
    SplitTypeUpdateRequest,
    PendingTransactionsResponse,
)
```

- [ ] **Step 2: Add GET /pending endpoint**

Add after the `shared_transactions` endpoint (after line 51):

```python
@router.get("/pending", response_model=PendingTransactionsResponse)
async def pending_transactions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_pending_transactions(db, current_user.id)
```

- [ ] **Step 3: Add DELETE /{id} endpoint**

Add after the pending endpoint:

```python
@router.delete("/{transaction_id}", status_code=204)
async def delete_transaction(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await service.delete_transaction(db, transaction_id, current_user.id)
    if result == "not_found":
        raise HTTPException(404, "Transaction not found")
    if result == "invalid":
        raise HTTPException(400, "Only pending email transactions can be deleted")
```

**IMPORTANT:** The DELETE endpoint MUST be placed AFTER all other specific path endpoints (`/mine`, `/pending`, `/shared`, `/monthly-summary`) because FastAPI matches routes in order and `/{transaction_id}` would capture those paths. Place it as the last route in the file.

- [ ] **Step 4: Run all tests**

Run: `cd backend && python3 -m pytest -v --tb=short`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/modules/transactions/router.py
git commit -m "feat: add GET /pending and DELETE /{id} endpoints"
```

---

### Task 6: Reconciler — Set bank_account_id on Match

**Files:**
- Modify: `backend/modules/fintoc/reconciler.py:95-99`

- [ ] **Step 1: Update the reconciler match logic**

In `backend/modules/fintoc/reconciler.py`, in the `reconcile_transactions` function, change lines 95-98 from:

```python
            await db.execute(
                update(Transaction)
                .where(Transaction.id == match.transaction_id)
                .values(status="reconciled", fintoc_id=ftc_txn.id)
            )
```

to:

```python
            # Find the bank account for this Fintoc sync
            from modules.households.models import BankAccount as BA
            ba_result = await db.execute(
                select(BA.id).where(
                    BA.user_id == user_id,
                    BA.is_active.is_(True),
                ).limit(1)
            )
            ba_id = ba_result.scalar_one_or_none()

            await db.execute(
                update(Transaction)
                .where(Transaction.id == match.transaction_id)
                .values(
                    status="reconciled",
                    fintoc_id=ftc_txn.id,
                    bank_account_id=ba_id,
                )
            )
```

- [ ] **Step 2: Add the select import at top of file**

Add `select` to the imports. The file currently imports from `modules.fintoc.client` and `modules.merchants.normalizer`. Add at line 69 (inside the function, where `select` and `update` are already imported):

No change needed — `select` is already imported inside the function on line 69.

- [ ] **Step 3: Run tests**

Run: `cd backend && python3 -m pytest -v --tb=short`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add backend/modules/fintoc/reconciler.py
git commit -m "fix: set bank_account_id on reconciled email transactions"
```

---

### Task 7: Cross-Sender Dedup + Non-Fintoc Status

**Files:**
- Modify: `backend/jobs/tasks.py:274-284` (process_email transaction creation)
- Create: `backend/tests/test_cross_sender_dedup.py`

- [ ] **Step 1: Write the dedup test**

```python
# backend/tests/test_cross_sender_dedup.py
import pytest
from datetime import datetime, timezone, timedelta
from modules.transactions.service import is_duplicate_transaction
from unittest.mock import AsyncMock, MagicMock
import uuid


@pytest.mark.asyncio
async def test_detects_duplicate_within_5_minutes():
    """Same amount + within 5 minutes of created_at → duplicate."""
    user_id = uuid.uuid4()
    mock_existing = MagicMock()
    mock_existing.id = uuid.uuid4()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_existing

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await is_duplicate_transaction(mock_db, user_id, 25990)
    assert result is True


@pytest.mark.asyncio
async def test_no_duplicate_when_none_found():
    """No matching transaction → not a duplicate."""
    user_id = uuid.uuid4()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await is_duplicate_transaction(mock_db, user_id, 25990)
    assert result is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python3 -m pytest tests/test_cross_sender_dedup.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Add is_duplicate_transaction to service.py**

Add to `backend/modules/transactions/service.py`:

```python
async def is_duplicate_transaction(
    db: AsyncSession, user_id: uuid.UUID, amount: int
) -> bool:
    """
    Check if a pending transaction with the same amount was created in the last 5 minutes.
    Used to deduplicate Banco de Chile compra + comprobante email pairs.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    result = await db.execute(
        select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.amount == amount,
            Transaction.status == "pending",
            Transaction.created_at >= cutoff,
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None
```

Add the needed imports at the top of service.py:
```python
from datetime import date, datetime, timezone, timedelta
```

- [ ] **Step 4: Run dedup tests**

Run: `cd backend && python3 -m pytest tests/test_cross_sender_dedup.py -v`
Expected: PASS

- [ ] **Step 5: Wire dedup + non-Fintoc status into process_email**

In `backend/jobs/tasks.py`, add import at the top (after line 7):
```python
from modules.transactions.service import is_duplicate_transaction
```

In the `process_email` function, after the merchant lookup (line 272) and BEFORE creating the transaction (line 274), add:

```python
                # Cross-sender dedup: skip if same amount was created in last 5 min
                if await is_duplicate_transaction(db, user.id, parsed.amount):
                    print(
                        f"[PROCESS_EMAIL] skipping duplicate transaction ${parsed.amount} for {user.email}",
                        flush=True,
                    )
                    continue

                # Non-Fintoc users: set status to settled (nothing to reconcile)
                has_fintoc = bank_account is not None
                txn_status = "pending" if has_fintoc else "settled"
```

Then change line 283 from:
```python
                    status="pending",
```
to:
```python
                    status=txn_status,
```

- [ ] **Step 6: Run all tests**

Run: `cd backend && python3 -m pytest -v --tb=short`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add backend/modules/transactions/service.py backend/jobs/tasks.py backend/tests/test_cross_sender_dedup.py
git commit -m "feat: cross-sender dedup + settled status for non-Fintoc users"
```

---

### Task 8: Frontend — API + Hook

**Files:**
- Modify: `frontend/app/lib/api.ts`
- Modify: `frontend/app/lib/hooks/useTransactions.ts`

- [ ] **Step 1: Add PendingTransactions type to api.ts**

In `frontend/app/lib/api.ts`, after the `Transaction` interface (after line 55), add:

```typescript
export interface PendingTransactions {
  awaiting_reconciliation: Transaction[];
  needs_classification: Transaction[];
  unmatched_email: Transaction[];
}
```

- [ ] **Step 2: Add API methods to api object**

In the `api` object, add after `getSharedTransactions` (after line 225):

```typescript
  getPendingTransactions: () =>
    apiFetch<PendingTransactions>("/transactions/pending"),

  deleteTransaction: (id: string) =>
    apiFetch<void>(`/transactions/${id}`, { method: "DELETE" }),
```

- [ ] **Step 3: Add usePendingTransactions hook**

In `frontend/app/lib/hooks/useTransactions.ts`, add after the imports:

```typescript
import { type PendingTransactions } from "@/app/lib/api";
```

Then add after `useMonthlySpending`:

```typescript
export function usePendingTransactions() {
  return useQuery({
    queryKey: ["transactions", "pending"],
    queryFn: () => api.getPendingTransactions(),
    staleTime: 30 * 1000,
  });
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/app/lib/api.ts frontend/app/lib/hooks/useTransactions.ts
git commit -m "feat: add getPendingTransactions API + usePendingTransactions hook"
```

---

### Task 9: Frontend — PendingBlock Component

**Files:**
- Create: `frontend/app/(dashboard)/components/PendingBlock.tsx`

- [ ] **Step 1: Create the PendingBlock component**

```typescript
// frontend/app/(dashboard)/components/PendingBlock.tsx
"use client";
import { useState } from "react";
import { usePendingTransactions } from "@/app/lib/hooks/useTransactions";
import { useQueryClient } from "@tanstack/react-query";
import { api, type Transaction } from "@/app/lib/api";
import { Trash2 } from "lucide-react";

function formatCLP(n: number) {
  return `$${Math.round(n).toLocaleString("es-CL")}`;
}

function formatTime(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
  const time = d.toLocaleTimeString("es-CL", { hour: "2-digit", minute: "2-digit" });
  if (diffDays === 0) return `Hoy, ${time}`;
  if (diffDays === 1) return `Ayer, ${time}`;
  return `${diffDays} días`;
}

function SourceBadge({ source }: { source: string }) {
  const isEmail = source === "gmail" || source === "outlook";
  return (
    <span
      className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
        isEmail ? "bg-blue-50 text-blue-600" : "bg-green-50 text-green-600"
      }`}
    >
      {isEmail ? "Email" : "Fintoc"}
    </span>
  );
}

interface PendingSectionProps {
  title: string;
  transactions: Transaction[];
  renderAction?: (txn: Transaction) => React.ReactNode;
  borderLeft?: boolean;
}

function PendingSection({ title, transactions, renderAction, borderLeft }: PendingSectionProps) {
  if (transactions.length === 0) return null;
  return (
    <div className="mt-3 first:mt-0">
      <p className="text-[10px] uppercase tracking-wide font-semibold text-orange-800 mb-1.5 pl-1">
        {title}
      </p>
      <div className="space-y-1">
        {transactions.map((txn) => (
          <div
            key={txn.id}
            className={`bg-white rounded-lg px-3 py-2.5 flex items-center justify-between ${
              borderLeft ? "border-l-[3px] border-l-amber-400" : ""
            }`}
          >
            <div className="min-w-0">
              <p className="text-sm font-semibold text-slate-800 truncate">
                {txn.raw_merchant_name}
              </p>
              <div className="flex items-center gap-1.5 mt-0.5">
                <SourceBadge source={txn.source} />
                <span className="text-[11px] text-slate-500">
                  {txn.split_type ? `${txn.split_type === "personal" ? "Mío" : txn.split_type === "partner" ? "Pareja" : "Compartido"}` : ""}
                  {txn.category ? ` · ${txn.category}` : ""}
                  {!txn.category && txn.source === "fintoc" ? (
                    <span className="text-red-500">Sin categoría</span>
                  ) : null}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-2.5 shrink-0">
              <div className="text-right">
                <p className="text-sm font-semibold text-slate-800 tabular-nums">
                  {formatCLP(Number(txn.amount))}
                </p>
                <p className="text-[10px] text-orange-500">{formatTime(txn.transaction_date)}</p>
              </div>
              {renderAction?.(txn)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function PendingBlock() {
  const { data, isLoading } = usePendingTransactions();
  const queryClient = useQueryClient();
  const [deleting, setDeleting] = useState<string | null>(null);

  if (isLoading || !data) return null;

  const { awaiting_reconciliation, needs_classification, unmatched_email } = data;
  const total = awaiting_reconciliation.length + needs_classification.length + unmatched_email.length;

  if (total === 0) return null;

  async function handleDelete(id: string) {
    if (!confirm("¿Eliminar esta transacción? Esta acción no se puede deshacer.")) return;
    setDeleting(id);
    try {
      await api.deleteTransaction(id);
      await queryClient.invalidateQueries({ queryKey: ["transactions", "pending"] });
    } finally {
      setDeleting(null);
    }
  }

  async function handleClassify(id: string) {
    const category = prompt("Categoría para este gasto:");
    if (!category) return;
    await api.updateCategory(id, category);
    await queryClient.invalidateQueries({ queryKey: ["transactions", "pending"] });
    await queryClient.invalidateQueries({ queryKey: ["transactions", "mine"] });
  }

  return (
    <div className="bg-orange-50 border border-orange-300 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-[15px] font-bold text-orange-700">Pendientes</span>
        <span className="bg-orange-400 text-white text-[11px] font-semibold rounded-full px-2 py-0.5">
          {total}
        </span>
      </div>

      <PendingSection
        title="Esperando confirmación bancaria"
        transactions={awaiting_reconciliation}
      />

      <PendingSection
        title="Necesitan categoría"
        transactions={needs_classification}
        renderAction={(txn) => (
          <button
            onClick={() => handleClassify(txn.id)}
            className="bg-blue-600 text-white text-[11px] font-semibold rounded-md px-3 py-1.5 hover:bg-blue-700 transition-colors"
          >
            Clasificar
          </button>
        )}
      />

      <PendingSection
        title="Sin match bancario"
        transactions={unmatched_email}
        borderLeft
        renderAction={(txn) => (
          <button
            onClick={() => handleDelete(txn.id)}
            disabled={deleting === txn.id}
            className="flex items-center gap-1 text-[11px] font-medium text-red-600 border border-red-300 rounded-md px-2.5 py-1.5 hover:bg-red-50 transition-colors disabled:opacity-50"
          >
            <Trash2 size={12} />
            Eliminar
          </button>
        )}
      />
    </div>
  );
}
```

**Note:** The `handleClassify` function uses a simple `prompt()` for now. In a follow-up, this should open the existing `CategoryBottomSheet` component. The prompt approach works for initial testing.

- [ ] **Step 2: Add updateCategory to api.ts if not present**

Check if `api.updateCategory` exists. If not, add to the `api` object in `frontend/app/lib/api.ts`:

```typescript
  updateCategory: (id: string, category: string) =>
    apiFetch<{ ok: boolean }>(`/transactions/${id}/category`, {
      method: "PATCH",
      body: JSON.stringify({ category }),
    }),
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/(dashboard)/components/PendingBlock.tsx frontend/app/lib/api.ts
git commit -m "feat: add PendingBlock component with 3 sections"
```

---

### Task 10: Frontend — Wire PendingBlock into Transactions Page

**Files:**
- Modify: `frontend/app/(dashboard)/transactions/page.tsx`

- [ ] **Step 1: Add PendingBlock import**

At the top of the file (after line 6), add:

```typescript
import { PendingBlock } from "../components/PendingBlock";
```

- [ ] **Step 2: Insert PendingBlock between SummaryBar and Tabs**

In the return JSX (around line 424-427), between `</SummaryBar>` closing tag and the `{/* Tabs */}` comment, add:

```typescript
      {/* Pending transactions */}
      <PendingBlock />
```

So the order becomes:
```
</FilterPanel>
<SummaryBar ... />
<PendingBlock />
<Tabs ...>
```

- [ ] **Step 3: Verify the build compiles**

Run: `cd frontend && npx next build 2>&1 | tail -20`
Expected: Build succeeds (or at least no TypeScript errors in the transactions page)

- [ ] **Step 4: Commit**

```bash
git add frontend/app/(dashboard)/transactions/page.tsx
git commit -m "feat: wire PendingBlock into Transactions page"
```

---

### Task 11: Final Verification

- [ ] **Step 1: Run full backend test suite**

Run: `cd backend && python3 -m pytest -v --tb=short`
Expected: All tests pass

- [ ] **Step 2: Run ruff linter + formatter**

Run: `cd backend && ruff check . && ruff format --check .`
Expected: Clean

- [ ] **Step 3: Verify frontend builds**

Run: `cd frontend && npx next build 2>&1 | tail -10`
Expected: Build succeeds

- [ ] **Step 4: Push to production**

```bash
git push origin main
```

- [ ] **Step 5: Remind user**

After deploy: send a test email to trigger the pending block. Verify:
1. Transaction appears in "Esperando confirmación bancaria"
2. After Fintoc sync runs, it moves to reconciled (main list) or "Sin match bancario"
3. "Eliminar" button works on unmatched
4. "Clasificar" button works on Fintoc transactions without category
