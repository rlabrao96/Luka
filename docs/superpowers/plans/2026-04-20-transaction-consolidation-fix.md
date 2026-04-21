# Transaction Consolidation Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the transaction consolidation workflow end-to-end so email-sourced pending transactions reconcile reliably with Plaid, CC bill payments get typed as transfers with both legs linked, same-account refund pairs get detected and netted out of totals, and the user has UI actions to manually link / dismiss / bulk-resolve pending rows.

**Architecture:** Four phases. (1) Additive schema migration + status vocabulary rename + indexes. (2) Backend reconciliation pipeline: fix inverted CC counterpart, persist `card_last_four`, wire `detect_transfers()`, add refund detector, register a 15-minute `reconciliation_tick` ARQ job that retries aging pendings / detects pairs / ages out to `orphan`. (3) New API endpoints for manual match and bulk actions. (4) Frontend: PendingBlock overhaul with action menu / age badge / bulk select, new `LinkMatchDialog`, pair-linked rendering for transfers + refunds, unified currency formatter, a11y fixes.

**Tech Stack:** Backend — Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic, ARQ, Redis, pytest (`asyncio_mode=auto`, real DB). Frontend — Next.js 16 App Router, React 19, Tailwind 4, shadcn/ui, Zustand 5, TanStack Query 5.

**Spec:** `docs/superpowers/specs/2026-04-20-transaction-consolidation-fix-design.md`
**Review:** `docs/reviews/luka-review-2026-04-20-transaction-consolidation.md`

---

## File Structure

### Phase 1 — Data model
- **Create:** `backend/alembic/versions/039_transaction_consolidation_schema.py`

### Phase 2 — Backend pipeline
- **Modify:** `backend/modules/transactions/models.py` — add `card_last_four`, `refund_pair_id`, `orphaned_at`, `dismissed_by_user`; update `status` literal.
- **Create:** `backend/modules/reconciliation/refunds.py` — same-account refund detector.
- **Create:** `backend/modules/reconciliation/tick.py` — orchestrates the 4 passes of `reconciliation_tick`.
- **Modify:** `backend/modules/reconciliation/transfers.py` — add `user_id` + `currency` equality guards, skip same-account pairs (keep existing).
- **Modify:** `backend/modules/reconciliation/dedup.py` — currency/sign/account filters, `user_id` guard on `apply_match_and_delete_emails`, skip merchant ILIKE for transfer-typed email rows, propagate `transaction_type='transfer'` + null category.
- **Modify:** `backend/modules/plaid/sync.py` — fix inverted CC counterpart lookup (last-4 tier + corrected name match), route modify branch through mapper, write `status='settled'`, call `reconciliation_tick` functions at end.
- **Modify:** `backend/modules/plaid/mapper.py` — emit `status='settled'`.
- **Modify:** `backend/modules/email/parser.py` — extract `card_last_four` on CC-payment regex path, expose on `ParsedEmail`.
- **Modify:** `backend/modules/email/llm_parser.py` — already extracts `card_last_four`; ensure it threads through.
- **Modify:** email-ingest tx creation path (find via grep: `ParsedEmail` consumer) — persist `card_last_four` and eager-resolve `transfer_to_account_id`.
- **Modify:** `backend/modules/transactions/service.py` — `is_duplicate_transaction` add currency + `source_bank_name`; populate `unmatched_email` bucket; add `exclude_from_totals()` helper; aggregation queries use it.
- **Create:** `backend/jobs/reconciliation_tick.py` — ARQ task wrapper + worker_settings registration.
- **Modify:** `backend/worker.py` (or ARQ settings file) — register task + cron.
- **Create:** `backend/scripts/cleanup_rafael_pending.py` — one-time cleanup script with `--dry-run`.

### Phase 3 — API
- **Modify:** `backend/modules/transactions/router.py` — `/match-candidates`, `/link`, `/dismiss`, `/bulk-action`.
- **Modify:** `backend/modules/transactions/service.py` — `get_match_candidates`, `link_transaction`, `dismiss_transaction`, `bulk_action`.
- **Modify:** `backend/modules/transactions/schemas.py` — `MatchCandidate`, `LinkRequest`, `BulkActionRequest`.

### Phase 4 — Frontend
- **Modify:** `frontend/app/lib/currency.ts` — add `formatStoredAmount(amountCents, currency, locale?)` + ISO 4217 decimals map.
- **Modify:** `frontend/app/lib/api.ts` — add client methods for new endpoints.
- **Modify:** `frontend/app/lib/hooks/useTransactions.ts` — add `useLinkTransaction`, `useDismissTransaction`, `useBulkAction`, `useMatchCandidates`.
- **Create:** `frontend/app/(dashboard)/components/LinkMatchDialog.tsx`.
- **Create:** `frontend/app/(dashboard)/components/PairedTransactionCard.tsx`.
- **Modify:** `frontend/app/(dashboard)/components/PendingBlock.tsx` — action menu, age badge, bulk select, skeleton/error, a11y.
- **Modify:** `frontend/app/(dashboard)/components/TransactionCard.tsx` — negative `aria-label`, use `formatStoredAmount`.
- **Modify:** `frontend/app/(dashboard)/components/RecentTransactions.tsx` — client-side pair grouping.
- **Modify:** `frontend/app/(dashboard)/transactions/page.tsx` — use `formatStoredAmount`, fix missing useEffect dep.

### Tests (backend, pytest real DB)
- **Create:** `backend/tests/test_reconciliation_refunds.py`
- **Create:** `backend/tests/test_reconciliation_tick.py`
- **Create:** `backend/tests/test_plaid_cc_counterpart.py`
- **Create:** `backend/tests/test_link_dismiss_bulk.py`
- **Create:** `backend/tests/test_match_candidates.py`
- **Create:** `backend/tests/test_email_card_last_four.py`
- **Modify:** `backend/tests/test_email_parser.py`, `test_llm_parser.py`, `test_cross_sender_dedup.py` — add cases for currency/sign/account/transfer-type behavior.

---

## Conventions for every task

- TDD: write failing test → run → implement → run → commit.
- Reference skill: @superpowers:test-driven-development.
- Backend tests use pytest `asyncio_mode=auto`, real DB via existing `conftest.py` fixtures. No mocks for DB.
- Run targeted test first: `cd backend && pytest tests/test_XYZ.py::test_name -v`.
- Run full backend suite before each phase's final commit: `cd backend && pytest`.
- Commit after each task with conventional prefix: `feat:`, `fix:`, `test:`, `refactor:`, `docs:`, `chore:`.
- Frontend type-check after changes: `cd frontend && npm run typecheck` (or `tsc --noEmit`).

---

# Phase 1 — Data model

### Task 1.1: Alembic migration — new columns, indexes, status check

**Files:**
- Create: `backend/alembic/versions/039_transaction_consolidation_schema.py`
- Test: `backend/tests/test_migrations.py` (extend)

- [ ] **Step 1: Write the failing migration test**

```python
# Append to backend/tests/test_migrations.py
import pytest
from sqlalchemy import text

@pytest.mark.asyncio
async def test_migration_039_adds_consolidation_columns(db_session):
    result = await db_session.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='transactions'
        AND column_name IN ('card_last_four','refund_pair_id','orphaned_at','dismissed_by_user')
    """))
    cols = {r[0] for r in result.fetchall()}
    assert cols == {'card_last_four','refund_pair_id','orphaned_at','dismissed_by_user'}

@pytest.mark.asyncio
async def test_migration_039_status_check_constraint(db_session):
    with pytest.raises(Exception):  # CHECK violation
        await db_session.execute(text(
            "INSERT INTO transactions (id, user_id, household_id, amount, currency, "
            "transaction_date, transaction_type, status, source, source_type, split_type) "
            "VALUES (gen_random_uuid(), gen_random_uuid(), gen_random_uuid(), 100, 'USD', "
            "NOW(), 'expense', 'bogus_status', 'gmail', 'email', 'personal')"
        ))
        await db_session.commit()
```

- [ ] **Step 2: Run to verify failure** — `cd backend && pytest tests/test_migrations.py::test_migration_039_adds_consolidation_columns -v`. Expect FAIL.

- [ ] **Step 3: Write migration**

```python
# backend/alembic/versions/039_transaction_consolidation_schema.py
"""transaction consolidation schema

Revision ID: 039
Revises: 038
Create Date: 2026-04-20
"""
from alembic import op
import sqlalchemy as sa

revision = '039'
down_revision = '038'
branch_labels = None
depends_on = None

def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.add_column('transactions', sa.Column('card_last_four', sa.String(4), nullable=True))
    op.add_column('transactions', sa.Column('refund_pair_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('transactions', sa.Column('orphaned_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('transactions', sa.Column('dismissed_by_user', sa.Boolean(), nullable=False, server_default=sa.false()))

    # Status vocabulary: confirmed -> settled
    op.execute("UPDATE transactions SET status='settled' WHERE status='confirmed'")
    op.execute("ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_status_check")
    op.execute("ALTER TABLE transactions ADD CONSTRAINT transactions_status_check "
               "CHECK (status IN ('pending','settled','orphan'))")

    # Indexes
    op.create_index('ix_transactions_household_date',
                    'transactions', ['household_id', sa.text('transaction_date DESC')])
    op.create_index('ix_transactions_pending_user',
                    'transactions', ['user_id'],
                    postgresql_where=sa.text("status='pending'"))
    op.create_index('ix_transactions_transfer_pair',
                    'transactions', ['transfer_pair_id'],
                    postgresql_where=sa.text('transfer_pair_id IS NOT NULL'))
    op.create_index('ix_transactions_refund_pair',
                    'transactions', ['refund_pair_id'],
                    postgresql_where=sa.text('refund_pair_id IS NOT NULL'))
    op.execute("CREATE INDEX ix_transactions_merchant_trgm "
               "ON transactions USING gin (raw_merchant_name gin_trgm_ops)")

def downgrade():
    op.drop_index('ix_transactions_merchant_trgm', table_name='transactions')
    op.drop_index('ix_transactions_refund_pair', table_name='transactions')
    op.drop_index('ix_transactions_transfer_pair', table_name='transactions')
    op.drop_index('ix_transactions_pending_user', table_name='transactions')
    op.drop_index('ix_transactions_household_date', table_name='transactions')
    op.execute("ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_status_check")
    op.execute("ALTER TABLE transactions ADD CONSTRAINT transactions_status_check "
               "CHECK (status IN ('pending','confirmed','settled'))")
    op.drop_column('transactions', 'dismissed_by_user')
    op.drop_column('transactions', 'orphaned_at')
    op.drop_column('transactions', 'refund_pair_id')
    op.drop_column('transactions', 'card_last_four')
```

- [ ] **Step 4: Run migration** — `cd backend && alembic upgrade head`.
- [ ] **Step 5: Run tests** — `cd backend && pytest tests/test_migrations.py -v`. Expect PASS.
- [ ] **Step 6: Commit** — `git add backend/alembic/versions/039_* backend/tests/test_migrations.py && git commit -m "feat(db): consolidation schema — card_last_four, refund_pair_id, orphan status"`

### Task 1.2: Update ORM model

**Files:** Modify `backend/modules/transactions/models.py`.

- [ ] Add columns matching migration; update `status` type hint to `Literal['pending','settled','orphan']` wherever used.
- [ ] Verify `select(Transaction).limit(1)` returns no errors — run `pytest tests/test_transactions_api.py -v`.
- [ ] Commit: `refactor(models): add consolidation fields to Transaction`.

---

# Phase 2 — Backend reconciliation pipeline

### Task 2.1: `detect_refunds` — failing test first

**Files:**
- Create: `backend/modules/reconciliation/refunds.py`
- Create: `backend/tests/test_reconciliation_refunds.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_reconciliation_refunds.py
import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from backend.modules.transactions.models import Transaction
from backend.modules.reconciliation.refunds import detect_refunds

@pytest.mark.asyncio
async def test_refund_pair_same_account_opposite_signs_same_merchant(db_session, household_factory, bank_account_factory):
    hh = await household_factory()
    acc = await bank_account_factory(household=hh)
    charge = Transaction(
        id=uuid4(), user_id=hh.owner_id, household_id=hh.id, bank_account_id=acc.id,
        amount=-2743, currency='USD', raw_merchant_name='Uber Eats',
        transaction_date=datetime(2026, 4, 16, tzinfo=timezone.utc),
        transaction_type='expense', status='settled', source='plaid', source_type='plaid',
        split_type='personal',
    )
    refund = Transaction(
        id=uuid4(), user_id=hh.owner_id, household_id=hh.id, bank_account_id=acc.id,
        amount=2743, currency='USD', raw_merchant_name='Uber Eats',
        transaction_date=datetime(2026, 4, 17, tzinfo=timezone.utc),
        transaction_type='income', status='settled', source='plaid', source_type='plaid',
        split_type='personal',
    )
    db_session.add_all([charge, refund])
    await db_session.commit()

    paired = await detect_refunds(db_session, hh.id, lookback_days=90)

    assert paired == 1
    await db_session.refresh(charge); await db_session.refresh(refund)
    assert charge.refund_pair_id is not None
    assert charge.refund_pair_id == refund.refund_pair_id

@pytest.mark.asyncio
async def test_refund_does_not_pair_different_account(db_session, household_factory, bank_account_factory):
    hh = await household_factory()
    acc1 = await bank_account_factory(household=hh)
    acc2 = await bank_account_factory(household=hh)
    # ... same merchant, opposite signs, different accounts -> no pair
    # assert detect_refunds returns 0 and refund_pair_id remains None

@pytest.mark.asyncio
async def test_refund_does_not_pair_different_currency(...):
    ...

@pytest.mark.asyncio
async def test_refund_does_not_pair_outside_90d(...):
    ...

@pytest.mark.asyncio
async def test_refund_prefers_earliest_match_when_multiple_candidates(...):
    ...
```

- [ ] **Step 2: Run** — FAIL (module not found).

- [ ] **Step 3: Implement `refunds.py`**

```python
# backend/modules/reconciliation/refunds.py
"""Same-account refund/reversal pair detection."""
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.modules.transactions.models import Transaction

async def detect_refunds(
    session: AsyncSession, household_id: UUID, lookback_days: int = 90
) -> int:
    """Link same-account opposite-sign pairs with a shared refund_pair_id.

    Rules: same bank_account_id, same currency, same normalized raw_merchant_name,
    same abs(amount), opposite signs, refund transaction_date 0..lookback_days after
    charge's. Neither already in a pair.

    Returns number of new pairs created.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    result = await session.execute(
        select(Transaction)
        .where(
            Transaction.household_id == household_id,
            Transaction.transaction_date >= cutoff,
            Transaction.bank_account_id.is_not(None),
            Transaction.transfer_pair_id.is_(None),
            Transaction.refund_pair_id.is_(None),
            Transaction.status == 'settled',
        )
        .order_by(Transaction.transaction_date.asc())
    )
    txns = list(result.scalars())

    # Bucket by (bank_account_id, currency, normalized_merchant, abs(amount))
    def norm(s: str | None) -> str:
        return ' '.join((s or '').lower().split())

    from collections import defaultdict
    buckets: dict[tuple, list[Transaction]] = defaultdict(list)
    for t in txns:
        key = (t.bank_account_id, t.currency, norm(t.raw_merchant_name), abs(int(t.amount)))
        buckets[key].append(t)

    pairs = 0
    for key, items in buckets.items():
        charges = sorted([t for t in items if t.amount < 0], key=lambda t: t.transaction_date)
        refunds = sorted([t for t in items if t.amount > 0], key=lambda t: t.transaction_date)
        used_refunds: set = set()
        for c in charges:
            for r in refunds:
                if r.id in used_refunds:
                    continue
                delta = (r.transaction_date - c.transaction_date).days
                if 0 <= delta <= lookback_days:
                    pair_id = uuid4()
                    c.refund_pair_id = pair_id
                    r.refund_pair_id = pair_id
                    used_refunds.add(r.id)
                    pairs += 1
                    break
    if pairs:
        await session.flush()
    return pairs
```

- [ ] **Step 4: Run tests** — PASS.
- [ ] **Step 5: Commit** — `feat(reconciliation): add same-account refund pair detector`.

### Task 2.2: Fix `detect_transfers` — user_id + currency equality

**Files:** Modify `backend/modules/reconciliation/transfers.py`; tests in `backend/tests/test_reconciliation_tick.py` (new).

- [ ] **Step 1: Write failing tests**: transfers should NOT pair (a) cross-user same-household rows, (b) same-amount different-currency rows.
- [ ] **Step 2: Add guards in the pairing loop:** require `tx_a.user_id == tx_b.user_id` AND `tx_a.currency == tx_b.currency` before marking.
- [ ] **Step 3: Run tests** — PASS.
- [ ] **Step 4: Commit** — `fix(transfers): require user_id and currency equality in pair detection`.

### Task 2.3: Fix `dedup._find_single_match` — currency, sign, transfer skip

**Files:** Modify `backend/modules/reconciliation/dedup.py`; tests in `backend/tests/test_cross_sender_dedup.py` (extend).

- [ ] **Step 1: Add failing tests:** same-amount different-currency should NOT match; transfer-typed email with merchant "Pago Tarjeta ****3100" SHOULD match a Plaid "American Express" row (merchant filter skipped); opposite-sign mismatch should NOT match.
- [ ] **Step 2: Implement**

```python
# dedup.py _find_single_match — modify WHERE
conditions = [
    Transaction.user_id == user_id,
    Transaction.source_type == 'email',
    Transaction.status == 'pending',
    Transaction.currency == currency,  # NEW
    func.abs(Transaction.amount) == abs(amount),  # keep; but ALSO require sign parity:
    # email stores same sign convention as bank -> match signed amount directly:
    Transaction.amount == amount,  # NEW (replaces abs equality)
    Transaction.transaction_date.between(tx_date - timedelta(days=3), tx_date + timedelta(days=3)),
]
if incoming_transaction_type != 'transfer' and raw_merchant_name:
    # Use trigram similarity instead of leading-wildcard ILIKE
    conditions.append(
        func.similarity(Transaction.raw_merchant_name, raw_merchant_name) > 0.3
    )
```

- [ ] **Step 3: Run tests** — PASS.
- [ ] **Step 4: Commit** — `fix(dedup): currency equality, sign parity, skip merchant for transfers`.

### Task 2.4: `dedup.apply_match_and_delete_emails` — user_id guard + transfer propagation

**Files:** Modify `backend/modules/reconciliation/dedup.py`; extend dedup test.

- [ ] **Step 1: Failing test:** call with an `email_tx_id` belonging to a different user → should raise / not delete.
- [ ] **Step 2: Implement** — add `user_id: UUID` param; add `Transaction.user_id == user_id` to both DELETE and UPDATE TransactionSplit. Always overwrite bank's `transaction_type` to `'transfer'` when email had it, and null `category`.
- [ ] **Step 3:** Update sole call site in `plaid/sync.py` to pass `user_id=item.user_id`.
- [ ] **Step 4: Tests PASS.** Commit — `fix(dedup): user_id guard + transfer type propagation`.

### Task 2.5: Fix inverted CC counterpart lookup in `plaid/sync.py`

**Files:** Modify `backend/modules/plaid/sync.py`; create `backend/tests/test_plaid_cc_counterpart.py`.

- [ ] **Step 1: Failing test:** seed a household with AmEx `BankAccount.account_mask='3100'`. Call `is_plaid_transfer` (or the inlined logic) for a Plaid tx named `"Pago Tarjeta American Express"` with `category=['TRANSFER','CREDIT_CARD']`. Expect `transaction_type='transfer'` + `transfer_to_account_id=<amex.id>`.

- [ ] **Step 2: Implement — refactor `is_plaid_transfer` into a small helper**

```python
# plaid/sync.py
import re
_LAST4_RE = re.compile(r'(?<!\d)(\d{4})(?!\d)')

async def _resolve_transfer_counterpart(
    session, household_id, plaid_tx, accounts_by_mask: dict[str, UUID], accounts_by_name: list[tuple[str, UUID]]
) -> UUID | None:
    name = (plaid_tx.name or '').lower()
    # Tier 1: last-4 match
    for m in _LAST4_RE.finditer(plaid_tx.name or ''):
        mask = m.group(1)
        if mask in accounts_by_mask:
            return accounts_by_mask[mask]
    # Tier 2: bank name appears in merchant name (corrected direction)
    for bank_name, account_id in accounts_by_name:
        if bank_name and bank_name.lower() in name:
            return account_id
    return None

def _is_plaid_cc_payment(plaid_tx) -> bool:
    cats = [c.upper() for c in (plaid_tx.category or [])]
    name = (plaid_tx.name or '').lower()
    return (
        'TRANSFER' in cats or 'CREDIT_CARD' in cats
        or 'pago tarjeta' in name or 'online payment' in name or 'payment thank you' in name
    )
```

Load `accounts_by_mask` and `accounts_by_name` once at the top of `run_plaid_sync` from the already-loaded household accounts. On each inserted Plaid tx, if `_is_plaid_cc_payment`, resolve counterpart; when resolved, set `transaction_type='transfer'`, `category=None`, `transfer_to_account_id=counterpart`.

- [ ] **Step 3:** Also fix the modify-branch amount scaling — route through `map_plaid_transaction` rather than inlining `round(plaid_amount * -100)`.

- [ ] **Step 4: Tests PASS.** Commit — `fix(plaid): correct CC counterpart lookup (last-4 + inverted name match)`.

### Task 2.6: Plaid mapper — `status='settled'`

**Files:** Modify `backend/modules/plaid/mapper.py`.

- [ ] **Step 1: Failing test:** map a non-pending Plaid tx → expect `status='settled'` (currently `'confirmed'`).
- [ ] **Step 2:** Replace `'confirmed'` with `'settled'` in mapper and any other sync paths that write status.
- [ ] **Step 3:** Update `service.py` queries that read `status='confirmed'` if any remain (grep).
- [ ] **Step 4: Commit** — `fix(plaid): write status='settled' (canonical vocabulary)`.

### Task 2.7: Persist `card_last_four` from email parser

**Files:** Modify `backend/modules/email/parser.py`, `backend/modules/email/llm_parser.py`, the email-ingest consumer path that turns `ParsedEmail` into a `Transaction` row; create `backend/tests/test_email_card_last_four.py`.

- [ ] **Step 1: Failing test:** feed `_parse_cc_payment` a realistic CC payment email body with `****3100`; expect `ParsedEmail.card_last_four == '3100'`. Feed LLM parser output with `card_last_four` set; expect the inserted `Transaction.card_last_four` populated.
- [ ] **Step 2: Implement:**
  - `parser.py`: extract `(\d{4})` from the `Pago Tarjeta ****NNNN` match, assign to `ParsedEmail.card_last_four`.
  - Email ingest consumer: when creating the `Transaction`, set `card_last_four` and attempt eager resolution against `bank_accounts.account_mask` for the household → set `transfer_to_account_id` if found.
- [ ] **Step 3:** Tests PASS. Commit — `feat(email): persist card_last_four and eagerly resolve transfer_to_account_id`.

### Task 2.8: Reconciliation tick — orchestrator

**Files:**
- Create: `backend/modules/reconciliation/tick.py`
- Create: `backend/tests/test_reconciliation_tick.py`

- [ ] **Step 1: Failing tests** (one per pass):
  - Email-after-Plaid: a pending email row older than 5 min + an already-existing matching Plaid row → after tick, email is deleted and Plaid row enriched.
  - Transfer pass: seeded but no Plaid sync today → tick still detects pair.
  - Refund pass: same as §2.1 but via tick.
  - Aging pass: pending email older than 14 days + at least one `PlaidItem.last_sync_at > tx.created_at` → status becomes `'orphan'`, `orphaned_at` set.
  - Aging pass negative: pending email older than 14 days but no Plaid sync since → stays `pending` (don't orphan during bank outages).

- [ ] **Step 2: Implement**

```python
# backend/modules/reconciliation/tick.py
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from backend.modules.transactions.models import Transaction
from backend.modules.plaid.models import PlaidItem
from backend.modules.reconciliation.dedup import find_email_match, apply_match_and_delete_emails
from backend.modules.reconciliation.transfers import detect_transfers
from backend.modules.reconciliation.refunds import detect_refunds

async def reconciliation_tick_for_household(session: AsyncSession, household_id: UUID) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    # 1. Email-after-Plaid: for each pending email >5min old, retry match against Plaid rows.
    email_pendings = (await session.execute(
        select(Transaction).where(
            Transaction.household_id == household_id,
            Transaction.source_type == 'email',
            Transaction.status == 'pending',
            Transaction.created_at < now - timedelta(minutes=5),
        )
    )).scalars().all()
    rematched = 0
    for email_tx in email_pendings:
        match = await find_email_match(
            session, user_id=email_tx.user_id,
            amount=email_tx.amount, currency=email_tx.currency,
            raw_merchant_name=email_tx.raw_merchant_name, tx_date=email_tx.transaction_date,
            incoming_transaction_type=email_tx.transaction_type,
            # look for settled Plaid txns to match against (inverse direction):
            match_against='plaid_settled',
        )
        if match:
            await apply_match_and_delete_emails(session, bank_tx_id=match.bank_tx_id,
                email_tx_ids=[email_tx.id], enrichment=match.enrichment, user_id=email_tx.user_id)
            rematched += 1

    # 2. Transfer pass
    transfers = await detect_transfers(session, household_id, lookback_days=7)
    # 3. Refund pass
    refunds = await detect_refunds(session, household_id, lookback_days=90)

    # 4. Aging pass
    cutoff = now - timedelta(days=14)
    aged_candidates = (await session.execute(
        select(Transaction).where(
            Transaction.household_id == household_id,
            Transaction.source_type == 'email',
            Transaction.status == 'pending',
            Transaction.created_at < cutoff,
        )
    )).scalars().all()
    orphaned = 0
    for tx in aged_candidates:
        # Has any Plaid sync run for this user's PlaidItems since tx.created_at?
        sync_after = (await session.execute(
            select(PlaidItem.id).where(
                PlaidItem.user_id == tx.user_id,
                PlaidItem.last_sync_at > tx.created_at,
            ).limit(1)
        )).first()
        if sync_after:
            tx.status = 'orphan'
            tx.orphaned_at = now
            orphaned += 1

    await session.flush()
    return {'rematched': rematched, 'transfers': transfers, 'refunds': refunds, 'orphaned': orphaned}

async def reconciliation_tick_all_households(session: AsyncSession) -> dict[str, int]:
    from backend.modules.households.models import Household
    households = (await session.execute(select(Household.id))).scalars().all()
    totals = {'rematched': 0, 'transfers': 0, 'refunds': 0, 'orphaned': 0}
    for hid in households:
        result = await reconciliation_tick_for_household(session, hid)
        for k in totals: totals[k] += result[k]
        await session.commit()
    return totals
```

Note: this requires extending `find_email_match` to support an inverse direction (match against existing Plaid settled rows when the new arrival is the email). If the current `find_email_match` only handles the Plaid-arrives-second case, implement the missing symmetric helper as `find_plaid_match_for_email(session, email_tx)`.

- [ ] **Step 3:** Tests PASS. Commit — `feat(reconciliation): add reconciliation tick orchestrator (rematch + transfers + refunds + aging)`.

### Task 2.9: Register `reconciliation_tick` on ARQ slow worker

**Files:** Create `backend/jobs/reconciliation_tick.py`; modify `backend/worker.py` (or ARQ `WorkerSettings`).

- [ ] **Step 1:** Write `backend/jobs/reconciliation_tick.py`:

```python
from arq import cron
from backend.core.db import async_session
from backend.modules.reconciliation.tick import reconciliation_tick_all_households

async def run_reconciliation_tick(ctx):
    async with async_session() as session:
        return await reconciliation_tick_all_households(session)

reconciliation_tick_cron = cron(run_reconciliation_tick, minute={0, 15, 30, 45}, run_at_startup=False)
```

- [ ] **Step 2:** Register in slow-worker `WorkerSettings.cron_jobs` (check `backend/worker.py` for existing pattern; follow it).
- [ ] **Step 3:** Smoke test — start ARQ locally, wait for the next quarter-hour, confirm log. Or trigger manually via `arq ... --burst` with a test cron override.
- [ ] **Step 4: Commit** — `feat(jobs): register reconciliation_tick every 15min on slow worker`.

### Task 2.10: `is_duplicate_transaction` + `unmatched_email` + `exclude_from_totals`

**Files:** Modify `backend/modules/transactions/service.py`.

- [ ] **Step 1: Failing tests:**
  - `is_duplicate_transaction` must NOT flag a CLP 2,000 as duplicate of USD 2,000 within 5 min.
  - Tier 1 must NOT flag two same-amount txns from different banks within 5 min.
  - `get_pending_transactions` `unmatched_email` bucket must contain email rows with `status='orphan'` for the user.
  - `get_my_transactions` totals must exclude rows with `transfer_pair_id` / `refund_pair_id` / `status='orphan'`.
- [ ] **Step 2: Implement** — add currency + `source_bank_name` to both tiers; populate `unmatched_email` bucket with `Transaction.source_type=='email' AND status=='orphan'`; extract `exclude_from_totals(query)` helper and apply everywhere totals are summed.
- [ ] **Step 3:** Tests PASS. Commit — `fix(transactions): currency-aware dedup, orphan bucket, totals exclusion helper`.

### Task 2.11: One-time cleanup script for Rafael's account

**Files:** Create `backend/scripts/cleanup_rafael_pending.py`.

- [ ] **Step 1:** Implement the script using the tick primitives. Required: `--dry-run` flag that prints the planned actions without commit.

```python
# backend/scripts/cleanup_rafael_pending.py
import asyncio, sys
from sqlalchemy import select
from backend.core.db import async_session
from backend.modules.auth.models import User
from backend.modules.households.models import HouseholdMember
from backend.modules.reconciliation.tick import reconciliation_tick_for_household

RAFAEL_EMAIL = 'rafaellabra96@gmail.com'

async def main(dry_run: bool):
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.email == RAFAEL_EMAIL))).scalar_one()
        memberships = (await session.execute(
            select(HouseholdMember.household_id).where(HouseholdMember.user_id == user.id)
        )).scalars().all()
        print(f'Rafael user_id={user.id}, households={memberships}')
        for hid in memberships:
            result = await reconciliation_tick_for_household(session, hid)
            print(f'  household {hid}: {result}')
        if dry_run:
            await session.rollback()
            print('[dry-run] rolled back')
        else:
            await session.commit()
            print('committed')

if __name__ == '__main__':
    asyncio.run(main(dry_run='--dry-run' in sys.argv))
```

- [ ] **Step 2:** Test it locally first with `--dry-run` pointing at dev DB.
- [ ] **Step 3: Commit** — `feat(scripts): one-time cleanup for Rafael pending transactions`.

### Phase 2 gate

- [ ] Run `cd backend && pytest` — full suite green.
- [ ] Manually start backend + worker, trigger a Plaid sync on Rafael's dev account, confirm tick runs.

---

# Phase 3 — API endpoints

### Task 3.1: `GET /transactions/{id}/match-candidates`

**Files:** Modify `backend/modules/transactions/router.py`, `service.py`, `schemas.py`. Create `backend/tests/test_match_candidates.py`.

- [ ] **Step 1: Failing tests:**
  - Returns ≤20 ranked candidates scoped to caller's household.
  - Filters out already-paired (`transfer_pair_id IS NOT NULL OR refund_pair_id IS NOT NULL`).
  - Honors `abs(amount)` within 2% tolerance, `window_days` date window, currency equality.
  - 404 if pending_id not owned by caller.
- [ ] **Step 2: Implement** — schema `MatchCandidate`, service `get_match_candidates(session, user_id, pending_id, window_days)`, router endpoint.
- [ ] **Step 3:** Tests PASS. Commit — `feat(api): GET /transactions/{id}/match-candidates`.

### Task 3.2: `POST /transactions/{id}/link`

**Files:** Same module. Test: `backend/tests/test_link_dismiss_bulk.py`.

- [ ] **Step 1: Failing tests:**
  - Happy path — links two rows owned by caller, email row deleted, bank row enriched.
  - 403 when either row belongs to another user.
  - Idempotent — linking twice is a no-op / 409.
- [ ] **Step 2: Implement** using `apply_match_and_delete_emails` with the user_id guard from Task 2.4.
- [ ] **Step 3: Commit** — `feat(api): POST /transactions/{id}/link`.

### Task 3.3: `POST /transactions/{id}/dismiss`

- [ ] **Step 1: Failing tests:** sets `status='orphan'`, `orphaned_at=now`, `dismissed_by_user=true`; 403 on wrong owner.
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Commit** — `feat(api): POST /transactions/{id}/dismiss`.

### Task 3.4: `POST /transactions/bulk-action`

- [ ] **Step 1: Failing tests:** caps at 100 IDs, all-or-nothing ownership check, supports `dismiss` and `delete`, returns `{processed: N}`.
- [ ] **Step 2: Implement** — single query to verify `count(id) == len(ids) AND user_id = caller`; then bulk UPDATE or DELETE.
- [ ] **Step 3: Commit** — `feat(api): POST /transactions/bulk-action`.

### Phase 3 gate

- [ ] `cd backend && pytest` green. Smoke-test endpoints via `curl` or HTTPie against dev.

---

# Phase 4 — Frontend

### Task 4.1: Unified `formatStoredAmount`

**Files:** Modify `frontend/app/lib/currency.ts`.

- [ ] Add an ISO 4217 decimals map (0-decimal set: CLP, COP, PYG, CRC, JPY, KRW, VND, …). Export:

```ts
export function formatStoredAmount(amountCents: number, currency: string, locale?: string): string {
  const decimals = ZERO_DECIMAL.has(currency) ? 0 : 2;
  const value = decimals === 0 ? amountCents : amountCents / 100;
  return new Intl.NumberFormat(locale ?? 'es-CL', {
    style: 'currency', currency, minimumFractionDigits: decimals, maximumFractionDigits: decimals,
  }).format(Math.abs(value));
}
export function isNegativeStored(amountCents: number) { return amountCents < 0; }
```

- [ ] Replace the three duplicated formatters in `PendingBlock.tsx`, `TransactionCard.tsx`, `transactions/page.tsx` — import the single helper.
- [ ] `cd frontend && npm run typecheck`.
- [ ] Commit — `refactor(frontend): unified formatStoredAmount helper`.

### Task 4.2: API client + hooks

**Files:** Modify `frontend/app/lib/api.ts`, `frontend/app/lib/hooks/useTransactions.ts`.

- [ ] Add typed client methods: `getMatchCandidates(txnId, windowDays)`, `linkTransaction(pendingId, bankTxnId)`, `dismissTransaction(id)`, `bulkAction(ids, action)`.
- [ ] Add TanStack Query mutations with optimistic updates + `onSettled: invalidateQueries(['transactions'])` and `['transactions','pending']`.
- [ ] Commit — `feat(api-client): hooks for link/dismiss/bulk + match candidates`.

### Task 4.3: `LinkMatchDialog.tsx`

**Files:** Create `frontend/app/(dashboard)/components/LinkMatchDialog.tsx`.

- [ ] shadcn `Dialog`. Props: `pendingTxn`, `open`, `onOpenChange`.
- [ ] Fetches candidates; shows ranked list with amount, date (formatted via `formatStoredAmount` + locale date), merchant, account. Each is a full-width clickable row with `aria-label`.
- [ ] Empty state: "No encontramos coincidencias" + CTA "Marcar como resuelta" → fires `/dismiss`.
- [ ] On success: toast + close + invalidate queries.
- [ ] Commit — `feat(ui): LinkMatchDialog for manual pending↔bank match`.

### Task 4.4: `PendingBlock.tsx` overhaul

**Files:** Modify `frontend/app/(dashboard)/components/PendingBlock.tsx`.

- [ ] Per-row shadcn `DropdownMenu` with `Vincular…`, `Marcar como resuelta`, `Eliminar` (the last wrapped in `AlertDialog`). Available on BOTH `awaiting_reconciliation` AND `unmatched_email` buckets (fixes missing-delete bug).
- [ ] Age badge: compute `daysOld` from `created_at`. Tailwind classes: `<3d green`, `3-7 amber`, `≥8 red`. Tooltip "hace N días".
- [ ] Sort `awaiting_reconciliation` oldest-first.
- [ ] Bulk-select mode: header toggle → checkboxes appear → floating toolbar with action buttons. Wire to `bulkAction` mutation.
- [ ] Skeleton loader (shadcn `Skeleton`) during `isLoading`; error card with Retry on `isError`.
- [ ] `aria-expanded`, `aria-controls` on collapsible header.
- [ ] Migrate inline pills → shadcn `DropdownMenu`/`Select` for category and split; keyboard navigable.
- [ ] `aria-label="menos ${formatted}"` on negative amounts.
- [ ] Commit — `feat(ui): PendingBlock actions, age badge, bulk select, a11y`.

### Task 4.5: Pair-linked rendering

**Files:** Create `frontend/app/(dashboard)/components/PairedTransactionCard.tsx`; modify `RecentTransactions.tsx`.

- [ ] Grouping helper (pure function): `groupPairs(txns) -> (singles | pairs)[]`, keyed by `transfer_pair_id` or `refund_pair_id` when non-null.
- [ ] `PairedTransactionCard`: collapsed view shows title / subtitle / icon / abs amount; expand chevron reveals both legs using existing `TransactionCard`.
- [ ] Wire into `RecentTransactions` render loop. Un-paired items render via `TransactionCard` as before.
- [ ] Commit — `feat(ui): pair-linked rendering for transfers + refunds`.

### Task 4.6: TransactionCard + page polish

**Files:** Modify `frontend/app/(dashboard)/components/TransactionCard.tsx`, `transactions/page.tsx`.

- [ ] Negative amount `aria-label`.
- [ ] Fix `useEffect` missing dep (`selectedCurrency`).
- [ ] Replace local `formatAmount` with `formatStoredAmount`.
- [ ] Locale from `Intl.DateTimeFormat().resolvedOptions().locale` not hardcoded `es-CL`.
- [ ] Commit — `fix(ui): a11y + locale polish on transactions page`.

### Phase 4 gate

- [ ] `cd frontend && npm run typecheck && npm run lint`.
- [ ] Dev server → Rafael's account → verify: pending action menu works, age badges show, bulk-dismiss clears the 31 backlog, `LinkMatchDialog` picker works end-to-end, CC payment pair renders as one card, Uber Eats refund pair renders as one card with struck amount.

---

# Final verification

- [ ] Full backend suite: `cd backend && pytest`.
- [ ] Full frontend type-check: `cd frontend && npm run typecheck`.
- [ ] Browser-use smoke on Rafael's live account (Phase 4 gate).
- [ ] Update docs:
  - [ ] `ARCHITECTURE.md` — new `reconciliation/refunds.py`, tick job, status vocab, new columns.
  - [ ] `README.md` — feature tracking.
  - [ ] `NEXT-STEPS.md` — remove items addressed by this plan.
  - [ ] Mark this plan complete.
- [ ] Tag release, deploy backend to Railway (slow worker restart picks up tick), deploy frontend to Vercel.
- [ ] Run `backend/scripts/cleanup_rafael_pending.py --dry-run` → inspect → run for real.

---

## Risk checklist before each deploy

- Phase 1 alembic migration is reversible — `alembic downgrade -1` must work; tested locally first.
- Phase 2 code paths tolerate rows with `status='confirmed'` remaining (none should remain after Phase 1, but defensive) — add a one-time read fallback `status IN ('settled','confirmed')` for the first 24h if needed, then remove.
- Phase 2 ARQ job is idempotent (guarded by `pair_id IS NULL` / `status='pending'`); safe to run alongside webhooks.
- Phase 3 endpoints require valid auth; cross-user attempts return 403 not 404 (info-leak surface).
- Phase 4 pair grouping is client-side only; if server later filters out paired rows we must remove the grouping pass to avoid double-hiding.
