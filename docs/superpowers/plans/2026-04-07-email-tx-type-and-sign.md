# Email Transaction Type & Sign Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix email-sourced transactions to store correct transaction_type (expense/income) and negative amounts for expenses, so they display correctly in the UI and stay only in pending until bank reconciliation.

**Architecture:** Three changes: (1) Pass `transaction_type` from parsed email to Transaction model, (2) Store expenses as negative amounts (matching Plaid/Connect convention), (3) Fix the amount sign in the email parser output for expenses. Transfer type means inter-account/CC payments only — NOT person-to-person (Zelle, Venmo, etc.).

**Tech Stack:** Python, FastAPI, SQLAlchemy, Gemini LLM

---

## Context

### Current behavior (broken)
- Email parser (LLM + regex) extracts `transaction_type` but `process_email` in `tasks.py:322-334` **never passes it** to the Transaction constructor
- Email amounts are always stored **positive** — but Plaid/Connect store expenses as negative
- Frontend uses `amount < 0` to determine expense vs income (correct for Plaid, wrong for email)
- The "Delete It" issue: LLM waterfall failed (model names fixed separately), regex fallback extracted wrong merchant. When user categorized via WhatsApp, the tx status stayed "pending" — but it appeared in BOTH pending and main list, suggesting a **duplicate transaction** was created (double `process_email` invocation for same email)

### Desired behavior
- `transaction_type` from parser flows through to Transaction model
- Expenses stored as negative amounts (matches Plaid/Connect convention)
- Income stored as positive amounts
- Email transactions ONLY appear in pending section until reconciled by bank sync
- No duplicate transactions from double email processing

### Transfer type rules
- "transfer" = inter-account moves only (CC payments, account-to-account, ATM cash)
- Person-to-person payments (Zelle, Venmo) = "expense" or "income" based on direction
- The LLM prompt already distinguishes this correctly (line 82 of `llm_parser.py`)

### Key files
- `backend/jobs/tasks.py:319-338` — Transaction creation from parsed email
- `backend/modules/email/parser.py:175-198` — Regex parser (Chilean banks)
- `backend/modules/email/llm_parser.py:111-126` — LLM parser result mapping
- `backend/modules/email/template_parser.py` — Template parser
- `backend/modules/transactions/service.py:13-32` — Main transaction list query
- `backend/modules/transactions/service.py:210+` — Pending transaction query

---

### Task 1: Pass transaction_type and fix amount sign in process_email

**Files:**
- Modify: `backend/jobs/tasks.py:319-334`

- [ ] **Step 1: Write the failing test**

Create test that verifies process_email stores transaction_type and negative amount for expenses.

```python
# backend/tests/test_process_email_txtype.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_expense_email_stores_negative_amount_and_type():
    """Email expense should store negative amount and transaction_type='expense'."""
    from modules.email.parser import ParsedEmail

    parsed = ParsedEmail(
        amount=2500,
        raw_merchant="STARBUCKS",
        transaction_date=datetime.now(timezone.utc),
        bank_name="Bank of America",
        transaction_type="expense",
        currency="USD",
    )

    # The transaction should be created with:
    # - amount = -2500 (negative for expense)
    # - transaction_type = "expense"
    assert parsed.transaction_type == "expense"
    # When stored: amount should be negated for expenses
    stored_amount = -abs(parsed.amount) if parsed.transaction_type == "expense" else parsed.amount
    assert stored_amount == -2500


@pytest.mark.asyncio
async def test_income_email_stores_positive_amount():
    """Email income should store positive amount and transaction_type='income'."""
    from modules.email.parser import ParsedEmail

    parsed = ParsedEmail(
        amount=50000,
        raw_merchant="WIRE DEPOSIT",
        transaction_date=datetime.now(timezone.utc),
        bank_name="Bank of America",
        transaction_type="income",
        currency="USD",
    )

    stored_amount = -abs(parsed.amount) if parsed.transaction_type == "expense" else abs(parsed.amount)
    assert stored_amount == 50000
```

- [ ] **Step 2: Run test to verify it passes** (this is a unit logic test)

Run: `cd backend && python -m pytest tests/test_process_email_txtype.py -v`

- [ ] **Step 3: Modify process_email to pass transaction_type and fix amount sign**

In `backend/jobs/tasks.py`, around line 319-334, change:

```python
# BEFORE (broken):
txn_status = "pending"

# Create pending transaction
txn = Transaction(
    user_id=user.id,
    household_id=household_id,
    bank_account_id=bank_account.id if bank_account else None,
    raw_merchant_name=parsed.raw_merchant,
    amount=parsed.amount,
    currency=parsed.currency,
    transaction_date=parsed.transaction_date,
    source=provider,
    source_bank_name=inferred_bank,
    status=txn_status,
    raw_email_text=raw_email.body,
)
```

```python
# AFTER (fixed):
txn_status = "pending"
tx_type = getattr(parsed, "transaction_type", None) or "expense"

# Store expenses as negative, income as positive (matches Plaid/Connect convention)
stored_amount = -abs(parsed.amount) if tx_type == "expense" else abs(parsed.amount)

# Create pending transaction
txn = Transaction(
    user_id=user.id,
    household_id=household_id,
    bank_account_id=bank_account.id if bank_account else None,
    raw_merchant_name=parsed.raw_merchant,
    amount=stored_amount,
    currency=parsed.currency,
    transaction_date=parsed.transaction_date,
    source=provider,
    source_bank_name=inferred_bank,
    status=txn_status,
    transaction_type=tx_type,
    raw_email_text=raw_email.body,
)
```

- [ ] **Step 4: Run existing tests to verify nothing breaks**

Run: `cd backend && python -m pytest tests/ -v --timeout=30 -x`

- [ ] **Step 5: Commit**

```bash
git add backend/jobs/tasks.py backend/tests/test_process_email_txtype.py
git commit -m "fix: pass transaction_type and store negative amounts for email expenses"
```

---

### Task 2: Fix regex parser to detect BofA email types

**Files:**
- Modify: `backend/modules/email/parser.py:170-198`

The regex parser (Layer 3 fallback) currently only handles Chilean bank emails. For BofA "withdrawal over limit" alerts, it needs to detect the email type from the subject/body.

- [ ] **Step 1: Read the current regex parser**

Read: `backend/modules/email/parser.py` lines 150-200 to understand the current flow.

- [ ] **Step 2: Add subject-based transaction type detection**

BofA sends different alert types:
- "A withdrawal was made" / "purchase" / "charge" → expense
- "A deposit was made" / "direct deposit" / "credit" → income
- "A transfer was made" / "transfer between" → transfer (only if between own accounts)

Add a function to `backend/modules/email/parser.py`:

```python
_EXPENSE_SUBJECT_PATTERNS = re.compile(
    r"withdrawal|purchase|charge|debit|payment was made|compra|cargo|pago",
    re.IGNORECASE,
)
_INCOME_SUBJECT_PATTERNS = re.compile(
    r"deposit|credit was posted|received|abono|depósito|ingreso",
    re.IGNORECASE,
)
_TRANSFER_SUBJECT_PATTERNS = re.compile(
    r"transfer between|moved between|traspaso entre",
    re.IGNORECASE,
)


def _infer_transaction_type(subject: str, body: str) -> str:
    """Infer transaction type from email subject and body keywords."""
    text = f"{subject} {body}"
    if _TRANSFER_SUBJECT_PATTERNS.search(text):
        return "transfer"
    if _INCOME_SUBJECT_PATTERNS.search(text):
        return "income"
    if _EXPENSE_SUBJECT_PATTERNS.search(text):
        return "expense"
    return "expense"  # default assumption
```

- [ ] **Step 3: Wire _infer_transaction_type into the parse_bank_email function**

Where the regex parser currently sets `transaction_type = "expense"` (around line 182), replace with:

```python
transaction_type = _infer_transaction_type(subject, text)
```

Note: the `parse_bank_email` function signature needs access to the email subject. Check if it already receives it; if not, pass it through.

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/ -v --timeout=30 -x`

- [ ] **Step 5: Commit**

```bash
git add backend/modules/email/parser.py
git commit -m "feat: regex parser infers transaction type from email subject/body keywords"
```

---

### Task 3: Strengthen email dedup to prevent double processing

**Files:**
- Modify: `backend/jobs/tasks.py:235-243`

The current dedup uses Redis with 24h TTL on `message_id`. If Redis flushes or the same Gmail push notification fires twice quickly, duplicates occur.

- [ ] **Step 1: Add DB-level dedup check**

After the Redis check (line 242), add a DB check before creating the transaction:

```python
# In process_email, after Redis dedup check and before Transaction creation:
# DB-level dedup: check if a transaction with same amount, merchant, and date
# was created in the last 5 minutes for this user
from sqlalchemy import func as sa_func

recent_dup = await db.execute(
    select(Transaction.id).where(
        Transaction.user_id == user.id,
        Transaction.raw_merchant_name == parsed.raw_merchant,
        sa_func.abs(Transaction.amount) == abs(parsed.amount),
        Transaction.source_type == "email",
        Transaction.created_at >= datetime.now(timezone.utc) - timedelta(minutes=5),
    ).limit(1)
)
if recent_dup.scalar_one_or_none():
    print(f"[PROCESS_EMAIL] skipping DB-level duplicate for {parsed.raw_merchant}", flush=True)
    continue
```

Note: check if `Transaction` model has a `created_at` column. If not, use `transaction_date` with a tight window.

- [ ] **Step 2: Verify `is_duplicate_transaction` function**

Read `backend/jobs/tasks.py` to find the existing `is_duplicate_transaction` helper (line 312). It may already do this but be broken. Ensure it checks `abs(amount)` (sign-agnostic).

- [ ] **Step 3: Run tests**

Run: `cd backend && python -m pytest tests/ -v --timeout=30 -x`

- [ ] **Step 4: Commit**

```bash
git add backend/jobs/tasks.py
git commit -m "fix: add DB-level dedup to prevent duplicate email transactions"
```

---

### Task 4: Fix existing email transactions in DB

**Files:**
- No code changes — SQL migration only

- [ ] **Step 1: Fix amounts for existing email transactions**

Email transactions currently have positive amounts for expenses. Negate them:

```sql
-- Fix email expenses: make amounts negative
UPDATE transactions
SET amount = -abs(amount)
WHERE source_type = 'email'
  AND amount > 0
  AND transaction_type IS DISTINCT FROM 'income';

-- Set transaction_type for email transactions that don't have one
UPDATE transactions
SET transaction_type = 'expense'
WHERE source_type = 'email'
  AND transaction_type IS NULL;
```

- [ ] **Step 2: Delete duplicate "Delete It" transactions**

```sql
-- Find and remove duplicates (keep the one with category/split)
DELETE FROM transaction_splits WHERE transaction_id IN (
  SELECT id FROM transactions
  WHERE raw_merchant_name ILIKE '%delete it%'
);
DELETE FROM transactions WHERE raw_merchant_name ILIKE '%delete it%';
```

- [ ] **Step 3: Verify pending transactions don't appear in main list**

```sql
-- Should return 0 rows if the fix is correct
SELECT id, raw_merchant_name, status
FROM transactions
WHERE source_type = 'email' AND status = 'pending'
  AND id IN (
    SELECT id FROM transactions WHERE status != 'pending'
  );
```

- [ ] **Step 4: Commit**

```bash
git commit --allow-empty -m "fix: migrate existing email transactions to negative expense amounts"
```

---

### Task 5: Verify WhatsApp flow doesn't change pending status

**Files:**
- Read-only verification: `backend/modules/whatsapp/handler.py`

- [ ] **Step 1: Verify _save_split doesn't change status**

Read `backend/modules/whatsapp/handler.py` around `_save_split` (line 285-302). Confirm it does NOT set `txn.status = "confirmed"`. The WhatsApp categorization should only add split + category, keeping status as "pending".

This is already correct based on our investigation — just verify.

- [ ] **Step 2: Verify the WhatsApp alert formats amount correctly**

Check the WhatsApp sender (`backend/modules/whatsapp/sender.py`) to ensure it displays negative amounts correctly for expenses (e.g., shows "US$2,504.17" not "-US$2,504.17").

If the sender formats using `abs(amount)`, no change needed. If it shows the raw amount, it may need `abs()` wrapping since we're now storing negatives.

- [ ] **Step 3: Fix if needed and commit**

```bash
git add backend/modules/whatsapp/sender.py  # only if changed
git commit -m "fix: WhatsApp alert displays absolute amount for expenses"
```

---

## Summary of changes

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Merchant name "DELETE IT" | LLM models 404 (fixed separately) | Model names updated in prior commit |
| Amount positive for expenses | `process_email` doesn't negate expenses | Task 1: store `-abs(amount)` for expenses |
| No transaction_type on email txs | `process_email` doesn't pass `parsed.transaction_type` | Task 1: pass `transaction_type` to Transaction |
| Appears in both pending + main | Duplicate transaction from double processing | Task 3: DB-level dedup + Task 4: cleanup |
| Regex fallback doesn't detect type | Only Chilean transfer detection | Task 2: subject-based type inference |
