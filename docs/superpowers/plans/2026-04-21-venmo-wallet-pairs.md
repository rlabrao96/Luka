# Venmo / Wallet Funding-Pair Detection — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop double-counting Venmo payments funded by BofA (and future connected wallets) by pairing the funding leg on the bank side with the canonical expense on the wallet side.

**Architecture:** Extend the existing reconciliation tick with a new `detect_wallet_pairs` pass that allows **same-sign** amount matches within **±5 days**, gated on at least one leg being on a connected wallet account. The bank leg is re-typed to `transfer`; the wallet leg keeps its counterparty name as the canonical expense/income. No schema changes — reuses `transfer_pair_id`.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 async, pytest (`asyncio_mode=auto`), PostgreSQL (Supabase).

**Spec:** `docs/superpowers/specs/2026-04-21-venmo-wallet-pairs-design.md`

---

## File Structure

| File | Purpose | Status |
|---|---|---|
| `backend/modules/plaid/mapper.py` | Add `("depository","paypal") → "wallet"` to `ACCOUNT_KIND_MAP` | Modify |
| `backend/modules/reconciliation/wallets.py` | `is_wallet_account` predicate + `detect_wallet_pairs` | **Create** |
| `backend/modules/reconciliation/tick.py` | Slot the new pass between transfer and refund | Modify |
| `backend/tests/test_reconciliation_wallet_pairs.py` | 8 behavioral tests | **Create** |
| `backend/scripts/backfill_wallet_pairs.py` | One-time CLI backfill, dry-run by default | **Create** |

---

## Task 1: Predicate + Plaid subtype mapping

**Files:**
- Create: `backend/modules/reconciliation/wallets.py`
- Modify: `backend/modules/plaid/mapper.py` (the `ACCOUNT_KIND_MAP` dict near the top)
- Test: `backend/tests/test_reconciliation_wallet_pairs.py`

- [ ] **Step 1.1: Write the failing predicate test**

Add a new test file `backend/tests/test_reconciliation_wallet_pairs.py` starting with:

```python
"""Tests for wallet funding-pair detection (Venmo / PayPal / CashApp)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.reconciliation.wallets import detect_wallet_pairs, is_wallet_account
from modules.transactions.models import Transaction


async def _seed_user(db, *, currency: str = "USD") -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"wallet-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="Wallet Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency=currency,
    )
    db.add(user)
    await db.flush()
    return user


async def _seed_household(db, owner: User) -> Household:
    hh = Household(id=uuid.uuid4(), name="Wallet HH", type="individual")
    db.add(hh)
    await db.flush()
    db.add(HouseholdMember(household_id=hh.id, user_id=owner.id, role="owner"))
    await db.flush()
    return hh


async def _seed_account(
    db,
    household: Household,
    user: User,
    *,
    bank_name: str,
    account_kind: str | None = None,
    currency: str = "USD",
) -> BankAccount:
    acct = BankAccount(
        id=uuid.uuid4(),
        household_id=household.id,
        user_id=user.id,
        bank_name=bank_name,
        account_type="personal",
        account_kind=account_kind,
        currency=currency,
        is_active=True,
    )
    db.add(acct)
    await db.flush()
    return acct


def _txn(
    *,
    user: User,
    household: Household,
    account: BankAccount,
    amount: Decimal,
    merchant: str,
    currency: str = "USD",
    date: datetime,
) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=household.id,
        bank_account_id=account.id,
        raw_merchant_name=merchant,
        amount=amount,
        currency=currency,
        transaction_date=date,
        transaction_type="expense" if amount < 0 else "income",
        status="settled",
        source="plaid",
        source_type="plaid",
    )


@pytest.mark.asyncio
async def test_is_wallet_account_detects_venmo_by_bank_name(db):
    user = await _seed_user(db)
    hh = await _seed_household(db, user)
    venmo = await _seed_account(db, hh, user, bank_name="Venmo")
    bofa = await _seed_account(db, hh, user, bank_name="Bank of America", account_kind="checking_account")
    assert is_wallet_account(venmo) is True
    assert is_wallet_account(bofa) is False


@pytest.mark.asyncio
async def test_is_wallet_account_detects_by_account_kind(db):
    user = await _seed_user(db)
    hh = await _seed_household(db, user)
    wallet = await _seed_account(db, hh, user, bank_name="SomeThirdParty", account_kind="wallet")
    assert is_wallet_account(wallet) is True
```

- [ ] **Step 1.2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_reconciliation_wallet_pairs.py -v`
Expected: FAIL — `ModuleNotFoundError: modules.reconciliation.wallets`.

- [ ] **Step 1.3: Create the wallets module with the predicate**

Create `backend/modules/reconciliation/wallets.py`:

```python
"""Wallet funding-pair detection.

Wallets (Venmo, PayPal, CashApp) are pass-through user-owned accounts.
When a wallet payment is funded by a linked bank account, Luka receives
two same-sign transactions for the same economic event:

  BofA   "Venmo"          -$30.90    (funding leg)
  Venmo  "Nicolas Celasco" -$30.90    (real expense, with counterparty)

This module detects such pairs and marks the bank leg as a `transfer`,
leaving the wallet leg as the canonical expense/income. Handles both
directions (funding and cash-out) within a ±5-day window.
"""
from __future__ import annotations

from modules.households.models import BankAccount


_WALLET_BANK_NAMES = ("venmo", "paypal", "cash app", "cashapp")


def is_wallet_account(account: BankAccount) -> bool:
    """True if `account` is a connected wallet (Venmo / PayPal / CashApp).

    Detected via `account_kind == 'wallet'` (set by the Plaid mapper when
    subtype is 'paypal'), or by the account's `bank_name` containing a
    known wallet token (safety net for manually-added accounts).
    """
    if account.account_kind == "wallet":
        return True
    if account.bank_name is None:
        return False
    name = account.bank_name.lower()
    return any(token in name for token in _WALLET_BANK_NAMES)
```

- [ ] **Step 1.4: Extend the Plaid mapper**

Edit `backend/modules/plaid/mapper.py` — change `ACCOUNT_KIND_MAP` to:

```python
ACCOUNT_KIND_MAP = {
    ("depository", "checking"): "checking_account",
    ("depository", "savings"): "savings_account",
    ("credit", "credit card"): "credit_card",
    ("depository", "paypal"): "wallet",
}
```

- [ ] **Step 1.5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_reconciliation_wallet_pairs.py -v`
Expected: both tests PASS.

- [ ] **Step 1.6: Commit**

```bash
git add backend/modules/reconciliation/wallets.py backend/modules/plaid/mapper.py backend/tests/test_reconciliation_wallet_pairs.py
git commit -m "feat(reconciliation): add is_wallet_account predicate + Plaid wallet subtype"
```

---

## Task 2: Same-sign funding pair detection

**Files:**
- Modify: `backend/modules/reconciliation/wallets.py`
- Modify: `backend/tests/test_reconciliation_wallet_pairs.py`

- [ ] **Step 2.1: Write the failing test for the core funding-pair case**

Append to `test_reconciliation_wallet_pairs.py`:

```python
@pytest.mark.asyncio
async def test_same_sign_funding_pair_matches_bofa_to_venmo(db):
    """The Feb 6 / Feb 9 Nicolas Celasco case from the spec."""
    user = await _seed_user(db)
    hh = await _seed_household(db, user)
    bofa = await _seed_account(db, hh, user, bank_name="Bank of America", account_kind="checking_account")
    venmo = await _seed_account(db, hh, user, bank_name="Venmo")

    feb6 = datetime(2026, 2, 6, tzinfo=timezone.utc)
    feb9 = datetime(2026, 2, 9, tzinfo=timezone.utc)
    venmo_tx = _txn(
        user=user, household=hh, account=venmo,
        amount=Decimal("-30.90"), merchant="Nicolas Celasco", date=feb6,
    )
    bofa_tx = _txn(
        user=user, household=hh, account=bofa,
        amount=Decimal("-30.90"), merchant="VENMO *PAYMENT", date=feb9,
    )
    db.add_all([venmo_tx, bofa_tx])
    await db.flush()

    pairs = await detect_wallet_pairs(db, hh.id, lookback_days=30)
    assert pairs == 1

    await db.refresh(venmo_tx)
    await db.refresh(bofa_tx)
    assert venmo_tx.transfer_pair_id is not None
    assert venmo_tx.transfer_pair_id == bofa_tx.transfer_pair_id
    # Bank leg re-typed, wallet leg stays as expense with counterparty name.
    assert bofa_tx.transaction_type == "transfer"
    assert venmo_tx.transaction_type == "expense"
```

- [ ] **Step 2.2: Run to verify FAIL**

Run: `cd backend && pytest tests/test_reconciliation_wallet_pairs.py::test_same_sign_funding_pair_matches_bofa_to_venmo -v`
Expected: FAIL — `detect_wallet_pairs` does not exist.

- [ ] **Step 2.3: Implement `detect_wallet_pairs`**

Append to `backend/modules/reconciliation/wallets.py`:

```python
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from modules.transactions.models import Transaction

_PAIR_WINDOW_DAYS = 5


async def detect_wallet_pairs(
    session: AsyncSession,
    household_id: uuid.UUID,
    lookback_days: int = 30,
) -> int:
    """Pair wallet-funding transactions with their canonical wallet leg.

    Rules:
      * Same household, same user, same currency, same abs(amount) (cents-exact).
      * At least one leg is on a wallet account (Venmo / PayPal / CashApp).
      * The OTHER leg's merchant name references the wallet's bank_name
        (ILIKE substring) — e.g. a BofA row named 'VENMO *PAYMENT'.
      * Sign is NOT constrained: same-sign (funding) and opposite-sign (cash-out)
        are both accepted. This is the difference vs. detect_transfers.
      * Dates within ±5 days.
      * Neither leg already paired (transfer_pair_id or refund_pair_id set).

    On match: share a fresh transfer_pair_id; re-type the NON-wallet leg to
    'transfer'. The wallet leg keeps its expense/income type.

    Returns number of pairs created.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    # Load candidate rows + their accounts in one pass.
    from modules.households.models import BankAccount

    rows = (
        await session.execute(
            select(Transaction, BankAccount)
            .join(BankAccount, Transaction.bank_account_id == BankAccount.id)
            .where(
                Transaction.household_id == household_id,
                Transaction.transaction_date >= cutoff,
                Transaction.transfer_pair_id.is_(None),
                Transaction.refund_pair_id.is_(None),
                Transaction.bank_account_id.is_not(None),
            )
            .order_by(Transaction.transaction_date)
        )
    ).all()

    # Split into wallet-side and bank-side candidates.
    wallet_rows: list[tuple[Transaction, BankAccount]] = []
    bank_rows: list[tuple[Transaction, BankAccount]] = []
    for tx, acct in rows:
        (wallet_rows if is_wallet_account(acct) else bank_rows).append((tx, acct))

    if not wallet_rows or not bank_rows:
        return 0

    # Index wallet rows by (user_id, currency, abs_amount_cents) for O(1) lookup.
    def _cents(amount) -> int:
        return round(abs(float(amount)) * 100)

    wallet_index: dict[tuple, list[tuple[Transaction, BankAccount]]] = defaultdict(list)
    for tx, acct in wallet_rows:
        wallet_index[(tx.user_id, tx.currency, _cents(tx.amount))].append((tx, acct))

    matched_ids: set[uuid.UUID] = set()
    pairs_found = 0

    for bank_tx, bank_acct in bank_rows:
        if bank_tx.id in matched_ids:
            continue
        if bank_tx.raw_merchant_name is None:
            continue
        bank_merchant = bank_tx.raw_merchant_name.lower()

        key = (bank_tx.user_id, bank_tx.currency, _cents(bank_tx.amount))
        for wallet_tx, wallet_acct in wallet_index.get(key, ()):
            if wallet_tx.id in matched_ids:
                continue
            if wallet_acct.bank_name is None:
                continue
            # Merchant-name gate: bank row must reference this wallet.
            if wallet_acct.bank_name.lower() not in bank_merchant:
                continue
            # Window check.
            day_diff = abs((bank_tx.transaction_date - wallet_tx.transaction_date).days)
            if day_diff > _PAIR_WINDOW_DAYS:
                continue

            pair_id = uuid.uuid4()
            await session.execute(
                update(Transaction)
                .where(Transaction.id.in_([bank_tx.id, wallet_tx.id]))
                .values(transfer_pair_id=pair_id)
            )
            # Re-type ONLY the bank leg. Wallet leg stays as expense/income.
            await session.execute(
                update(Transaction)
                .where(Transaction.id == bank_tx.id)
                .values(transaction_type="transfer")
            )
            matched_ids.add(bank_tx.id)
            matched_ids.add(wallet_tx.id)
            pairs_found += 1
            break

    return pairs_found
```

- [ ] **Step 2.4: Move the `import` to module top**

The skeleton above uses `from modules.households.models import BankAccount` inside the function to avoid circular imports. Verify it's not causing a circular import — if not, move it to the top of the file alongside the other imports. If it does, leave it inline.

Run: `cd backend && python -c "from modules.reconciliation.wallets import detect_wallet_pairs"`
Expected: no output (success).

- [ ] **Step 2.5: Run to verify PASS**

Run: `cd backend && pytest tests/test_reconciliation_wallet_pairs.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 2.6: Commit**

```bash
git add backend/modules/reconciliation/wallets.py backend/tests/test_reconciliation_wallet_pairs.py
git commit -m "feat(reconciliation): detect same-sign wallet funding pairs"
```

---

## Task 3: Opposite-sign cash-out within ±5 days

**Files:**
- Modify: `backend/tests/test_reconciliation_wallet_pairs.py`

- [ ] **Step 3.1: Write failing test for 4-day ACH cash-out**

Append:

```python
@pytest.mark.asyncio
async def test_opposite_sign_cashout_within_5_days_matches(db):
    """Venmo cash-out to BofA that takes 4 calendar days to settle."""
    user = await _seed_user(db)
    hh = await _seed_household(db, user)
    bofa = await _seed_account(db, hh, user, bank_name="Bank of America", account_kind="checking_account")
    venmo = await _seed_account(db, hh, user, bank_name="Venmo")

    day0 = datetime(2026, 3, 1, tzinfo=timezone.utc)
    venmo_out = _txn(
        user=user, household=hh, account=venmo,
        amount=Decimal("-50.00"), merchant="Transfer to Bank", date=day0,
    )
    bofa_in = _txn(
        user=user, household=hh, account=bofa,
        amount=Decimal("50.00"), merchant="VENMO CASHOUT", date=day0 + timedelta(days=4),
    )
    db.add_all([venmo_out, bofa_in])
    await db.flush()

    pairs = await detect_wallet_pairs(db, hh.id, lookback_days=30)
    assert pairs == 1

    await db.refresh(venmo_out)
    await db.refresh(bofa_in)
    assert venmo_out.transfer_pair_id == bofa_in.transfer_pair_id
    assert bofa_in.transaction_type == "transfer"
    # Wallet leg keeps its original sign-derived type.
    assert venmo_out.transaction_type == "expense"
```

- [ ] **Step 3.2: Run — should already PASS**

Run: `cd backend && pytest tests/test_reconciliation_wallet_pairs.py::test_opposite_sign_cashout_within_5_days_matches -v`
Expected: PASS (the Task 2 implementation already covers opposite-sign since sign is unconstrained).

If it fails, the implementation is wrong — debug and fix before proceeding.

- [ ] **Step 3.3: Commit**

```bash
git add backend/tests/test_reconciliation_wallet_pairs.py
git commit -m "test(reconciliation): verify opposite-sign wallet cash-out within 5 days"
```

---

## Task 4: Negative-path tests (PayPal not connected, partial top-up, orphan wallet row, already paired, cross-household, cross-currency)

**Files:**
- Modify: `backend/tests/test_reconciliation_wallet_pairs.py`

- [ ] **Step 4.1: Write the six failing/passing negative tests at once**

Append:

```python
@pytest.mark.asyncio
async def test_paypal_merchant_without_paypal_account_does_not_pair(db):
    """Rafael has PayPal charges on BofA but no connected PayPal account.
    The row must stay as a real expense — merchant name alone must never pair.
    """
    user = await _seed_user(db)
    hh = await _seed_household(db, user)
    bofa = await _seed_account(db, hh, user, bank_name="Bank of America", account_kind="checking_account")
    # No PayPal/Venmo/CashApp account connected.

    day0 = datetime(2026, 2, 10, tzinfo=timezone.utc)
    bofa_tx = _txn(
        user=user, household=hh, account=bofa,
        amount=Decimal("-20.00"), merchant="PAYPAL *SOMETHING", date=day0,
    )
    unrelated = _txn(
        user=user, household=hh, account=bofa,
        amount=Decimal("-20.00"), merchant="Coffee Shop", date=day0 + timedelta(days=1),
    )
    db.add_all([bofa_tx, unrelated])
    await db.flush()

    pairs = await detect_wallet_pairs(db, hh.id, lookback_days=30)
    assert pairs == 0
    await db.refresh(bofa_tx)
    assert bofa_tx.transfer_pair_id is None
    assert bofa_tx.transaction_type == "expense"


@pytest.mark.asyncio
async def test_partial_topup_does_not_pair(db):
    """BofA tops up Venmo with $50 but Venmo only spends $30.90 — amounts differ."""
    user = await _seed_user(db)
    hh = await _seed_household(db, user)
    bofa = await _seed_account(db, hh, user, bank_name="Bank of America", account_kind="checking_account")
    venmo = await _seed_account(db, hh, user, bank_name="Venmo")

    day0 = datetime(2026, 2, 6, tzinfo=timezone.utc)
    venmo_tx = _txn(
        user=user, household=hh, account=venmo,
        amount=Decimal("-30.90"), merchant="Nicolas Celasco", date=day0,
    )
    bofa_tx = _txn(
        user=user, household=hh, account=bofa,
        amount=Decimal("-50.00"), merchant="VENMO *PAYMENT", date=day0 + timedelta(days=3),
    )
    db.add_all([venmo_tx, bofa_tx])
    await db.flush()

    pairs = await detect_wallet_pairs(db, hh.id, lookback_days=30)
    assert pairs == 0


@pytest.mark.asyncio
async def test_venmo_only_payment_with_no_bofa_leg_stays_unchanged(db):
    """Payment covered by Venmo balance — only the Venmo row exists."""
    user = await _seed_user(db)
    hh = await _seed_household(db, user)
    venmo = await _seed_account(db, hh, user, bank_name="Venmo")

    venmo_tx = _txn(
        user=user, household=hh, account=venmo,
        amount=Decimal("-10.00"), merchant="Alejandro Carrillo",
        date=datetime(2026, 2, 6, tzinfo=timezone.utc),
    )
    db.add(venmo_tx)
    await db.flush()

    pairs = await detect_wallet_pairs(db, hh.id, lookback_days=30)
    assert pairs == 0
    await db.refresh(venmo_tx)
    assert venmo_tx.transfer_pair_id is None
    assert venmo_tx.transaction_type == "expense"


@pytest.mark.asyncio
async def test_already_paired_rows_are_skipped(db):
    user = await _seed_user(db)
    hh = await _seed_household(db, user)
    bofa = await _seed_account(db, hh, user, bank_name="Bank of America", account_kind="checking_account")
    venmo = await _seed_account(db, hh, user, bank_name="Venmo")

    existing_pair = uuid.uuid4()
    day0 = datetime(2026, 2, 6, tzinfo=timezone.utc)
    venmo_tx = _txn(
        user=user, household=hh, account=venmo,
        amount=Decimal("-30.90"), merchant="Nicolas", date=day0,
    )
    venmo_tx.transfer_pair_id = existing_pair
    bofa_tx = _txn(
        user=user, household=hh, account=bofa,
        amount=Decimal("-30.90"), merchant="VENMO", date=day0 + timedelta(days=2),
    )
    db.add_all([venmo_tx, bofa_tx])
    await db.flush()

    pairs = await detect_wallet_pairs(db, hh.id, lookback_days=30)
    assert pairs == 0


@pytest.mark.asyncio
async def test_cross_household_isolation(db):
    user_a = await _seed_user(db)
    user_b = await _seed_user(db)
    hh_a = await _seed_household(db, user_a)
    hh_b = await _seed_household(db, user_b)

    venmo_a = await _seed_account(db, hh_a, user_a, bank_name="Venmo")
    bofa_b = await _seed_account(db, hh_b, user_b, bank_name="Bank of America", account_kind="checking_account")

    day0 = datetime(2026, 2, 6, tzinfo=timezone.utc)
    venmo_tx = _txn(
        user=user_a, household=hh_a, account=venmo_a,
        amount=Decimal("-30.90"), merchant="Nicolas", date=day0,
    )
    bofa_tx = _txn(
        user=user_b, household=hh_b, account=bofa_b,
        amount=Decimal("-30.90"), merchant="VENMO", date=day0 + timedelta(days=2),
    )
    db.add_all([venmo_tx, bofa_tx])
    await db.flush()

    assert await detect_wallet_pairs(db, hh_a.id, lookback_days=30) == 0
    assert await detect_wallet_pairs(db, hh_b.id, lookback_days=30) == 0


@pytest.mark.asyncio
async def test_cross_currency_does_not_pair(db):
    user = await _seed_user(db)
    hh = await _seed_household(db, user)
    bofa_usd = await _seed_account(db, hh, user, bank_name="Bank of America", currency="USD", account_kind="checking_account")
    venmo_clp = await _seed_account(db, hh, user, bank_name="Venmo", currency="CLP")

    day0 = datetime(2026, 2, 6, tzinfo=timezone.utc)
    venmo_tx = _txn(
        user=user, household=hh, account=venmo_clp,
        amount=Decimal("-3090"), merchant="Nicolas", currency="CLP", date=day0,
    )
    bofa_tx = _txn(
        user=user, household=hh, account=bofa_usd,
        amount=Decimal("-3090"), merchant="VENMO", currency="USD", date=day0 + timedelta(days=2),
    )
    db.add_all([venmo_tx, bofa_tx])
    await db.flush()

    pairs = await detect_wallet_pairs(db, hh.id, lookback_days=30)
    assert pairs == 0
```

- [ ] **Step 4.2: Run — all should PASS given the Task 2 implementation**

Run: `cd backend && pytest tests/test_reconciliation_wallet_pairs.py -v`
Expected: all 9 tests PASS.

If any fail, they indicate a gap in `detect_wallet_pairs` — fix the implementation (not the test) and re-run.

- [ ] **Step 4.3: Commit**

```bash
git add backend/tests/test_reconciliation_wallet_pairs.py
git commit -m "test(reconciliation): negative-path coverage for wallet pairs"
```

---

## Task 5: Wire into the reconciliation tick

**Files:**
- Modify: `backend/modules/reconciliation/tick.py`
- Modify: `backend/tests/test_reconciliation_tick.py` (add one tick-level test)

- [ ] **Step 5.1: Add tick-level integration test**

Append to `backend/tests/test_reconciliation_tick.py` (reuse its existing fixtures; inspect the file first for the style):

```python
@pytest.mark.asyncio
async def test_tick_detects_wallet_pairs(db):
    """The tick runs the wallet pass and reports pairs in its return dict."""
    # Use the same fixture helpers as the other tick tests.
    # Build: one BofA + one Venmo account, one same-sign matching pair.
    # Assert: tick returns wallet_pairs == 1, bank leg typed 'transfer'.
    ...  # flesh out using patterns from surrounding tests in this file
```

Read `backend/tests/test_reconciliation_tick.py` first to match its fixture conventions, then replace the `...` with a concrete test modeled on `test_same_sign_funding_pair_matches_bofa_to_venmo` but calling `reconciliation_tick_for_household` instead.

- [ ] **Step 5.2: Run — should FAIL (tick doesn't run the pass yet)**

Run: `cd backend && pytest tests/test_reconciliation_tick.py::test_tick_detects_wallet_pairs -v`
Expected: FAIL — `wallet_pairs` key missing from return dict.

- [ ] **Step 5.3: Wire the pass into the tick**

Edit `backend/modules/reconciliation/tick.py`:

1. Add import at the top:
   ```python
   from modules.reconciliation.wallets import detect_wallet_pairs
   ```

2. Insert a new pass between the transfer and refund passes. Replace:
   ```python
   # ---------- 2. Transfer pass.
   transfers = await detect_transfers(session, household_id, lookback_days=7)

   # ---------- 3. Refund pass.
   refunds = await detect_refunds(session, household_id, lookback_days=90)
   ```
   with:
   ```python
   # ---------- 2. Transfer pass (opposite-sign, ±2 days, own-account).
   transfers = await detect_transfers(session, household_id, lookback_days=7)

   # ---------- 3. Wallet-pair pass (same- or opposite-sign, ±5 days, wallet-gated).
   wallet_pairs = await detect_wallet_pairs(session, household_id, lookback_days=30)

   # ---------- 4. Refund pass.
   refunds = await detect_refunds(session, household_id, lookback_days=90)
   ```

3. Update the return dict:
   ```python
   return {
       "rematched": rematched,
       "transfers": transfers,
       "wallet_pairs": wallet_pairs,
       "refunds": refunds,
       "orphaned": orphaned,
   }
   ```

4. Update `reconciliation_tick_all_households` totals init:
   ```python
   totals = {"rematched": 0, "transfers": 0, "wallet_pairs": 0, "refunds": 0, "orphaned": 0}
   ```

- [ ] **Step 5.4: Run tick + wallet tests**

Run: `cd backend && pytest tests/test_reconciliation_tick.py tests/test_reconciliation_wallet_pairs.py tests/test_reconciliation_transfers.py -v`
Expected: all tests PASS.

- [ ] **Step 5.5: Commit**

```bash
git add backend/modules/reconciliation/tick.py backend/tests/test_reconciliation_tick.py
git commit -m "feat(reconciliation): wire wallet-pair detection into the tick"
```

---

## Task 6: Backfill CLI script

**Files:**
- Create: `backend/scripts/backfill_wallet_pairs.py`

- [ ] **Step 6.1: Write the script**

The backfill runs `detect_wallet_pairs` inside a transaction and, **before committing**, queries the freshly-paired rows (those with a `transfer_pair_id` that didn't exist at the start of the run) and prints a table. Without `--apply`, the transaction is rolled back. This gives a spec-faithful preview without duplicating the matching logic.

Create `backend/scripts/backfill_wallet_pairs.py`:

```python
"""One-time backfill: detect wallet funding pairs across a household's full history.

Dry-run by default — prints a table of candidate pairs, then rolls back.
Pass --apply to commit.

Usage:
    python -m scripts.backfill_wallet_pairs --email rafaellabra96@gmail.com
    python -m scripts.backfill_wallet_pairs --email rafaellabra96@gmail.com --apply
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid

from sqlalchemy import select

from core.database import AsyncSessionLocal

# Register ORM models for metadata resolution.
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
import modules.transactions.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, HouseholdMember
from modules.reconciliation.wallets import detect_wallet_pairs
from modules.transactions.models import Transaction

# 10 years covers all possible history; effectively "no cap".
_FULL_HISTORY_DAYS = 365 * 10


async def _snapshot_paired_ids(db, household_id: uuid.UUID) -> set[uuid.UUID]:
    """IDs of transactions already paired before the run."""
    ids = (
        await db.execute(
            select(Transaction.id).where(
                Transaction.household_id == household_id,
                Transaction.transfer_pair_id.is_not(None),
            )
        )
    ).scalars().all()
    return set(ids)


async def _print_new_pairs(db, household_id: uuid.UUID, pre_ids: set[uuid.UUID]) -> None:
    """Print a table of pairs created by this run (not present in pre_ids)."""
    rows = (
        await db.execute(
            select(Transaction, BankAccount)
            .join(BankAccount, Transaction.bank_account_id == BankAccount.id)
            .where(
                Transaction.household_id == household_id,
                Transaction.transfer_pair_id.is_not(None),
                Transaction.id.not_in(pre_ids) if pre_ids else True,
            )
            .order_by(Transaction.transfer_pair_id, Transaction.transaction_date)
        )
    ).all()

    # Group by transfer_pair_id.
    by_pair: dict[uuid.UUID, list] = {}
    for tx, acct in rows:
        by_pair.setdefault(tx.transfer_pair_id, []).append((tx, acct))

    if not by_pair:
        return

    header = f"{'pair':>4} | {'date':>10} | {'amount':>10} | {'account':<24} | merchant"
    print(header)
    print("-" * len(header))
    for i, (_pid, legs) in enumerate(by_pair.items(), start=1):
        for tx, acct in legs:
            print(
                f"{i:>4} | {tx.transaction_date.date().isoformat():>10} | "
                f"{float(tx.amount):>10.2f} | {(acct.bank_name or '')[:24]:<24} | "
                f"{tx.raw_merchant_name or ''}"
            )


async def main(email: str, apply_changes: bool) -> int:
    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if user is None:
            print(f"No user with email {email}", file=sys.stderr)
            return 1

        household_ids = (
            await db.execute(
                select(HouseholdMember.household_id).where(HouseholdMember.user_id == user.id)
            )
        ).scalars().all()

        if not household_ids:
            print(f"User {email} has no households", file=sys.stderr)
            return 1

        total_pairs = 0
        for hid in household_ids:
            pre_ids = await _snapshot_paired_ids(db, hid)
            pairs = await detect_wallet_pairs(db, hid, lookback_days=_FULL_HISTORY_DAYS)
            print(f"\nHousehold {hid}: {pairs} wallet pair(s) detected")
            if pairs:
                await _print_new_pairs(db, hid, pre_ids)
            total_pairs += pairs

        if apply_changes:
            await db.commit()
            print(f"\nCOMMITTED {total_pairs} pair(s).")
        else:
            await db.rollback()
            print(f"\nDRY RUN — {total_pairs} pair(s) would be created. Re-run with --apply.")

        return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--email", default="rafaellabra96@gmail.com")
    ap.add_argument("--apply", action="store_true", help="Commit changes (default: dry-run)")
    args = ap.parse_args()
    sys.exit(asyncio.run(main(args.email, args.apply)))
```

- [ ] **Step 6.2: Smoke-test the script (dry-run)**

Run: `cd backend && python -m scripts.backfill_wallet_pairs --email rafaellabra96@gmail.com`
Expected: prints one line per household with a pair count, ends with "DRY RUN — N pair(s) would be created."

**STOP HERE.** Do not pass `--apply` yet. Hand off to the user to eyeball the count and spot-check a couple of transactions in the feed. If the count looks sane (~handful of Venmo pairs from Feb), user re-runs with `--apply`.

- [ ] **Step 6.3: Commit**

```bash
git add backend/scripts/backfill_wallet_pairs.py
git commit -m "feat(scripts): CLI backfill for wallet funding pairs"
```

---

## Task 7: Final verification

- [ ] **Step 7.1: Run the full reconciliation test suite**

Run:
```bash
cd backend && pytest tests/test_reconciliation_transfers.py tests/test_reconciliation_wallet_pairs.py tests/test_reconciliation_tick.py tests/test_reconciliation_refunds.py tests/test_reconciliation_dedup.py -v
```
Expected: all green.

- [ ] **Step 7.2: Push branch**

```bash
git push
```

- [ ] **Step 7.3: Hand off to user for the `--apply` run**

Tell Rafael:
1. Run `python -m scripts.backfill_wallet_pairs --email rafaellabra96@gmail.com` and note the pair count.
2. Spot-check the BofA "Venmo" rows in the feed — they should still be displayed.
3. If the count matches expectation, re-run with `--apply`.
4. Verify Feb dashboard totals drop by the double-counted amount.

---

## Notes

- **No migration required.** Reuses `transfer_pair_id`.
- **No feature flag.** The wallet-gated predicate makes it a no-op for households without wallets.
- **Going forward.** The tick runs on every cron (existing schedule); new Venmo pairs pair automatically within ±5 days of settlement.
- **PayPal safety.** If Rafael ever connects PayPal, the same logic just starts working — nothing else to change.
