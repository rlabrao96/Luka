# Partner-Card Charge Attribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a household member hand off individual transactions on a shared authorized-user card to their partner, so a handed-off charge becomes the partner's personal expense (and a payment feeds a per-person card balance), with an approve/reject notification flow.

**Architecture:** A new `transaction_attributions` table holds one row per handed-off transaction (recipient, sender, status). The charge stays a single row on the sender's account; the sender's totals already exclude `split_type='partner'`, and the recipient's queries gain a predicate that *includes* transactions with an `active` attribution to them. An `effective_owner` helper keeps the sender-excludes / recipient-includes halves in sync. Notifications reuse the existing `notifications` table and the `merchant_review` approve/reject UI pattern.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async, Alembic, pytest (`asyncio_mode=auto`, real DB), Next.js 16 + React 19 + TanStack Query.

**Spec:** `docs/superpowers/specs/2026-07-12-partner-card-charge-attribution-design.md`

**Conventions to honor (from CLAUDE.md):**
- Amounts are integer minor units; never hand-roll ×100.
- One totals-exclusion rule lives in `modules/transactions/totals.py`.
- `split_type='partner'` is already excluded from the owner's totals (dashboard, budgets, categories).
- `mark_user_edited(txn, "split_type")` protects manual split edits from re-sync.
- Tests hit a real DB via the savepoint-rollback `db` fixture in `backend/tests/conftest.py`. Register models with `import module.models  # noqa: F401` so FKs resolve on flush.
- Run backend commands from `backend/` with `uv run`. Lint before commit: `uv run ruff check <files> && uv run ruff format <files>`. Commit with `--no-verify` (pre-commit hook conflicts with staged edits — known in this repo). Frontend typecheck: `npx tsc --noEmit` from `frontend/`.
- Commit trailers on every commit:
  ```
  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01KTzzogYq2HwKtDuvJttYFa
  ```

---

## File Structure

**Phase 1 — core hand-off**
- `backend/alembic/versions/054_transaction_attributions.py` — Create: table + unique(transaction_id) + indexes.
- `backend/modules/transactions/models.py` — Modify: add `TransactionAttribution` model.
- `backend/modules/transactions/attribution.py` — Create: attribution domain logic (resolve recipient, create/upsert, reject, un-tag, `effective_owner`, the recipient-inclusion predicate). Kept in its own file so `service.py` doesn't grow further and the logic is holdable in one context.
- `backend/modules/transactions/service.py` — Modify: `get_my_transactions` + `get_dashboard_summary` owner predicate to include attributed-active-to-caller.
- `backend/modules/budgets/v2_queries.py` — Modify: personal-view predicate to include attributed-active-to-caller.
- `backend/modules/transactions/router.py` — Modify: add attribute / reject / un-attribute endpoints.
- `backend/modules/households/service.py` — Modify: revert active attributions when a member leaves.
- `frontend/app/lib/api.ts` — Modify: types + `attributeTransaction` / `rejectAttribution` / `unattributeTransaction` calls; notification payload fields.
- `frontend/app/(dashboard)/components/SplitTypeEditor.tsx` — Modify: "De mi pareja" calls the attribute endpoint.
- `frontend/app/(dashboard)/notifications/page.tsx` — Modify: `charge_attributed` (Confirmar / No es mío) + `attribution_rejected` (informational) rendering.
- Tests: `backend/tests/test_transaction_attribution.py` (lifecycle, predicate, privacy, leave-household).

**Phase 2 — per-person card balance**
- `backend/modules/transactions/attribution.py` — Modify: `account_person_balances(db, bank_account_id)`.
- `backend/modules/bank_accounts/router.py` — Modify: expose balances on the account detail response (or a dedicated sub-route).
- `frontend/app/(dashboard)/settings/components/BankAccountsSection.tsx` — Modify: render the per-person balance block on a card that has attributions.
- Tests: `backend/tests/test_account_person_balances.py`.

---

# PHASE 1 — Core hand-off

### Task 1: `transaction_attributions` table + model

**Files:**
- Create: `backend/alembic/versions/054_transaction_attributions.py`
- Modify: `backend/modules/transactions/models.py` (after `TransactionSplit`, ~line 84)
- Test: `backend/tests/test_transaction_attribution.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_transaction_attribution.py
"""Partner-card charge attribution — lifecycle, predicate, privacy.
Real DB, savepoint-rollback ``db`` fixture (no mocks, per CLAUDE.md)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

import modules.merchants.models  # noqa: F401
import modules.notifications.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.transactions.models import Transaction, TransactionAttribution, TransactionSplit


async def _couple(db):
    """Rafael (owner) + Camila (member) in one household; returns (rafael, camila, hh)."""
    hh = Household(id=uuid.uuid4(), name="HH", type="couple")
    db.add(hh)
    await db.flush()
    users = {}
    for name, role in (("rafael", "owner"), ("camila", "member")):
        u = User(
            id=uuid.uuid4(),
            email=f"{name}-{uuid.uuid4().hex[:8]}@luka.test",
            full_name=name.title(),
            email_provider="gmail",
            whatsapp_verified=False,
            preferred_currency="USD",
        )
        db.add(u)
        await db.flush()
        db.add(HouseholdMember(household_id=hh.id, user_id=u.id, role=role))
        users[name] = u
    await db.flush()
    return users["rafael"], users["camila"], hh


async def _charge(db, owner, hh, amount="-40.00"):
    txn = Transaction(
        id=uuid.uuid4(),
        user_id=owner.id,
        household_id=hh.id,
        raw_merchant_name="Sephora",
        amount=Decimal(amount),
        currency="USD",
        transaction_date=datetime.now(timezone.utc),
        source="plaid",
        source_type="plaid",
        status="settled",
        transaction_type="expense",
    )
    db.add(txn)
    await db.flush()
    return txn


async def test_attribution_row_persists(db):
    rafael, camila, hh = await _couple(db)
    txn = await _charge(db, rafael, hh)
    db.add(
        TransactionAttribution(
            transaction_id=txn.id,
            attributed_to_user_id=camila.id,
            attributed_by_user_id=rafael.id,
            status="active",
        )
    )
    await db.flush()
    row = (
        await db.execute(
            select(TransactionAttribution).where(TransactionAttribution.transaction_id == txn.id)
        )
    ).scalar_one()
    assert row.status == "active"
    assert row.attributed_to_user_id == camila.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_transaction_attribution.py::test_attribution_row_persists -v`
Expected: FAIL — `ImportError: cannot import name 'TransactionAttribution'`.

- [ ] **Step 3: Add the model**

```python
# backend/modules/transactions/models.py — add after TransactionSplit (~line 84)
class TransactionAttribution(Base):
    """A transaction on a shared card handed off to a household partner.

    One row per transaction (unique). 'active' → counts for the recipient;
    'rejected' → bounced back to the sender (row kept so a re-hand-off can
    reactivate it). The row's presence is what distinguishes a handed-off
    ``split_type='partner'`` transaction from an exclude-only one.
    """

    __tablename__ = "transaction_attributions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id"), nullable=False, unique=True
    )
    attributed_to_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    attributed_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")  # active|rejected
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 4: Write the migration**

```python
# backend/alembic/versions/054_transaction_attributions.py
"""054 — transaction_attributions (partner-card charge hand-off)

Revision ID: 054
Revises: 053
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "054"
down_revision: Union[str, Sequence[str], None] = "053"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "transaction_attributions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "transaction_id",
            UUID(as_uuid=True),
            sa.ForeignKey("transactions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "attributed_to_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "attributed_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # Recipient's inbox / inclusion predicate lookups.
    op.create_index(
        "ix_txn_attr_recipient_active",
        "transaction_attributions",
        ["attributed_to_user_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_txn_attr_recipient_active", table_name="transaction_attributions")
    op.drop_table("transaction_attributions")
```

- [ ] **Step 5: Apply migration and run the test**

Run: `cd backend && uv run alembic upgrade head && uv run pytest tests/test_transaction_attribution.py::test_attribution_row_persists -v`
Expected: `alembic` shows `Running upgrade 053 -> 054`; test PASSES.
> ⚠️ `.env` `DATABASE_URL` points at PRODUCTION. This migration only creates a new empty table (no data change), which is safe, but confirm with the user before running `alembic upgrade head` against prod.

- [ ] **Step 6: Lint & commit**

```bash
cd backend && uv run ruff check modules/transactions/models.py alembic/versions/054_transaction_attributions.py tests/test_transaction_attribution.py && uv run ruff format modules/transactions/models.py alembic/versions/054_transaction_attributions.py tests/test_transaction_attribution.py
cd .. && git add backend/modules/transactions/models.py backend/alembic/versions/054_transaction_attributions.py backend/tests/test_transaction_attribution.py
git commit --no-verify -m "feat(attribution): transaction_attributions table + model

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01KTzzogYq2HwKtDuvJttYFa"
```

---

### Task 2: `effective_owner` + recipient-inclusion predicate

**Files:**
- Create: `backend/modules/transactions/attribution.py`
- Test: `backend/tests/test_transaction_attribution.py`

- [ ] **Step 1: Write the failing test** (append)

```python
async def test_effective_owner_and_predicate(db):
    from modules.transactions.attribution import attributed_to_clause, effective_owner_id

    rafael, camila, hh = await _couple(db)
    txn = await _charge(db, rafael, hh)
    attr = TransactionAttribution(
        transaction_id=txn.id,
        attributed_to_user_id=camila.id,
        attributed_by_user_id=rafael.id,
        status="active",
    )
    db.add(attr)
    await db.flush()

    assert effective_owner_id(rafael.id, attr) == camila.id
    assert effective_owner_id(rafael.id, None) == rafael.id
    attr.status = "rejected"
    assert effective_owner_id(rafael.id, attr) == rafael.id  # rejected → back to owner

    # Predicate: Camila's rows = her own OR active-attributed-to-her.
    attr.status = "active"
    await db.flush()
    rows = (
        await db.execute(
            select(Transaction.id)
            .outerjoin(
                TransactionAttribution,
                TransactionAttribution.transaction_id == Transaction.id,
            )
            .where(attributed_to_clause(camila.id))
        )
    ).scalars().all()
    assert txn.id in rows
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_transaction_attribution.py::test_effective_owner_and_predicate -v`
Expected: FAIL — `ModuleNotFoundError: modules.transactions.attribution`.

- [ ] **Step 3: Implement the helpers**

```python
# backend/modules/transactions/attribution.py
"""Partner-card charge attribution: hand off a transaction on a shared card to
a household partner. See docs/superpowers/specs/2026-07-12-partner-card-charge-attribution-design.md.
"""
from __future__ import annotations

import uuid

from sqlalchemy import or_

from modules.transactions.models import Transaction, TransactionAttribution


def effective_owner_id(owner_user_id: uuid.UUID, attribution: TransactionAttribution | None):
    """Who a transaction's amount counts for: the recipient when actively
    attributed, otherwise the account/transaction owner."""
    if attribution is not None and attribution.status == "active":
        return attribution.attributed_to_user_id
    return owner_user_id


def owned_by_caller_clause(caller_id: uuid.UUID):
    """A transaction counts for ``caller_id`` when it is their own row and NOT
    actively attributed away, OR it is actively attributed TO them.

    Requires the query to ``outerjoin(TransactionAttribution)``. This is the
    single predicate both the caller-excludes and recipient-includes sides use,
    guaranteeing exactly-one-owner by construction.
    """
    attributed_away = (TransactionAttribution.id.isnot(None)) & (
        TransactionAttribution.status == "active"
    )
    own_kept = (Transaction.user_id == caller_id) & (~attributed_away)
    return or_(own_kept, attributed_to_clause(caller_id))


def attributed_to_clause(caller_id: uuid.UUID):
    """Rows actively attributed to ``caller_id``. Requires outerjoin(TransactionAttribution)."""
    return (TransactionAttribution.attributed_to_user_id == caller_id) & (
        TransactionAttribution.status == "active"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_transaction_attribution.py::test_effective_owner_and_predicate -v`
Expected: PASS.

- [ ] **Step 5: Lint & commit**

```bash
cd backend && uv run ruff check modules/transactions/attribution.py tests/test_transaction_attribution.py && uv run ruff format modules/transactions/attribution.py tests/test_transaction_attribution.py
cd .. && git add backend/modules/transactions/attribution.py backend/tests/test_transaction_attribution.py
git commit --no-verify -m "feat(attribution): effective_owner + recipient-inclusion predicate

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01KTzzogYq2HwKtDuvJttYFa"
```

---

### Task 3: Attribution domain ops — resolve recipient, hand off (upsert), reject, un-tag

**Files:**
- Modify: `backend/modules/transactions/attribution.py`
- Test: `backend/tests/test_transaction_attribution.py`

Behavior (from spec §2, §6):
- `resolve_recipient(db, household_id, sender_id)` → the single other active member's id, or `None` if zero, or raises `AmbiguousRecipient` (list attached) if >1.
- `hand_off(db, txn, sender_id, recipient_id)`: set `split_type='partner'` on the txn's split via the existing `update_split_type` path (so `mark_user_edited` fires), **upsert** the attribution (reactivate a `rejected` row → `active`, clear `acknowledged_at`; else insert), and create a `charge_attributed` notification to the recipient. Idempotent if already active to the same recipient.
- `reject(db, attribution_id, by_user_id)`: guard `attributed_to_user_id == by_user_id`; set `status='rejected'`; revert split to `personal`; notify sender (`attribution_rejected`).
- `un_tag(db, txn_id, by_user_id)`: guard `attributed_by_user_id == by_user_id`; delete the row; revert split to `personal`; if it had `acknowledged_at`, notify recipient (`attribution_removed`).

- [ ] **Step 1: Write failing tests** (append) — covers hand_off, reject-bounce, re-hand-off upsert, un_tag, resolve_recipient.

```python
async def test_hand_off_reject_and_re_handoff(db):
    from modules.notifications.models import Notification
    from modules.transactions.attribution import hand_off, reject, resolve_recipient

    rafael, camila, hh = await _couple(db)
    txn = await _charge(db, rafael, hh)
    # seed the default personal split the app always creates
    db.add(TransactionSplit(transaction_id=txn.id, split_type="personal"))
    await db.flush()

    assert await resolve_recipient(db, hh.id, rafael.id) == camila.id

    await hand_off(db, txn, sender_id=rafael.id, recipient_id=camila.id)
    await db.flush()
    attr = (
        await db.execute(
            select(TransactionAttribution).where(TransactionAttribution.transaction_id == txn.id)
        )
    ).scalar_one()
    assert attr.status == "active"
    split = (
        await db.execute(
            select(TransactionSplit).where(TransactionSplit.transaction_id == txn.id)
        )
    ).scalar_one()
    assert split.split_type == "partner"
    notif = (
        await db.execute(
            select(Notification).where(Notification.type == "charge_attributed")
        )
    ).scalar_one()
    assert notif.user_id == camila.id

    # Camila rejects → bounces back to Rafael's personal, sender notified.
    await reject(db, attr.id, by_user_id=camila.id)
    await db.flush()
    await db.refresh(attr)
    await db.refresh(split)
    assert attr.status == "rejected"
    assert split.split_type == "personal"
    assert (
        await db.execute(
            select(Notification).where(Notification.type == "attribution_rejected")
        )
    ).scalar_one().user_id == rafael.id

    # Rafael re-hands-off → SAME row reactivated (unique constraint respected).
    await hand_off(db, txn, sender_id=rafael.id, recipient_id=camila.id)
    await db.flush()
    rows = (
        await db.execute(
            select(TransactionAttribution).where(TransactionAttribution.transaction_id == txn.id)
        )
    ).scalars().all()
    assert len(rows) == 1 and rows[0].status == "active"
```

- [ ] **Step 2: Run to verify fail**

Run: `cd backend && uv run pytest tests/test_transaction_attribution.py::test_hand_off_reject_and_re_handoff -v`
Expected: FAIL — `ImportError` (hand_off/reject/resolve_recipient not defined).

- [ ] **Step 3: Implement the ops**

```python
# backend/modules/transactions/attribution.py — append
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.households.models import HouseholdMember
from modules.notifications.service import create_notification
from modules.transactions.models import TransactionSplit


class AmbiguousRecipient(Exception):
    """More than one other active member — caller must choose."""

    def __init__(self, candidate_ids: list[uuid.UUID]):
        self.candidate_ids = candidate_ids
        super().__init__("multiple candidate recipients")


async def resolve_recipient(db, household_id, sender_id):
    ids = (
        await db.execute(
            select(HouseholdMember.user_id).where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.user_id != sender_id,
                HouseholdMember.left_at.is_(None),
            )
        )
    ).scalars().all()
    if not ids:
        return None
    if len(ids) > 1:
        raise AmbiguousRecipient(list(ids))
    return ids[0]


async def _set_split(db, transaction_id, split_type, decided_by):
    split = (
        await db.execute(
            select(TransactionSplit).where(TransactionSplit.transaction_id == transaction_id)
        )
    ).scalar_one_or_none()
    if split:
        split.split_type = split_type
        split.decided_by_user_id = decided_by
        split.decided_at = datetime.now(timezone.utc)
    else:
        db.add(
            TransactionSplit(
                transaction_id=transaction_id,
                split_type=split_type,
                decided_by_user_id=decided_by,
                decided_at=datetime.now(timezone.utc),
            )
        )


async def hand_off(db: AsyncSession, txn, sender_id, recipient_id):
    """Tag the txn as the recipient's (split=partner) + upsert attribution + notify."""
    from modules.transactions.service import mark_user_edited

    await _set_split(db, txn.id, "partner", sender_id)
    mark_user_edited(txn, "split_type")

    attr = (
        await db.execute(
            select(TransactionAttribution).where(
                TransactionAttribution.transaction_id == txn.id
            )
        )
    ).scalar_one_or_none()
    if attr is None:
        attr = TransactionAttribution(
            transaction_id=txn.id,
            attributed_to_user_id=recipient_id,
            attributed_by_user_id=sender_id,
            status="active",
        )
        db.add(attr)
    else:
        attr.attributed_to_user_id = recipient_id
        attr.attributed_by_user_id = sender_id
        attr.status = "active"
        attr.acknowledged_at = None
    await db.flush()

    await create_notification(
        db,
        user_id=recipient_id,
        type="charge_attributed",
        title=f"{txn.raw_merchant_name} — ¿es tuyo?",
        payload={
            "transaction_id": str(txn.id),
            "attribution_id": str(attr.id),
            "merchant": txn.raw_merchant_name,
            "amount": txn.amount if isinstance(txn.amount, int) else str(txn.amount),
            "currency": txn.currency,
        },
    )


async def reject(db: AsyncSession, attribution_id, by_user_id):
    attr = (
        await db.execute(
            select(TransactionAttribution).where(TransactionAttribution.id == attribution_id)
        )
    ).scalar_one_or_none()
    if attr is None or attr.attributed_to_user_id != by_user_id:
        return False
    attr.status = "rejected"
    attr.acknowledged_at = None
    txn = (
        await db.execute(select(Transaction).where(Transaction.id == attr.transaction_id))
    ).scalar_one()
    await _set_split(db, txn.id, "personal", by_user_id)
    await db.flush()
    await create_notification(
        db,
        user_id=attr.attributed_by_user_id,
        type="attribution_rejected",
        title=f"{txn.raw_merchant_name} vuelve a tus gastos",
        payload={
            "transaction_id": str(txn.id),
            "merchant": txn.raw_merchant_name,
            "amount": txn.amount if isinstance(txn.amount, int) else str(txn.amount),
            "currency": txn.currency,
        },
    )
    return True


async def un_tag(db: AsyncSession, transaction_id, by_user_id):
    attr = (
        await db.execute(
            select(TransactionAttribution).where(
                TransactionAttribution.transaction_id == transaction_id
            )
        )
    ).scalar_one_or_none()
    if attr is None or attr.attributed_by_user_id != by_user_id:
        return False
    recipient, was_ack = attr.attributed_to_user_id, attr.acknowledged_at is not None
    await db.delete(attr)
    await _set_split(db, transaction_id, "personal", by_user_id)
    await db.flush()
    if was_ack:
        txn = (
            await db.execute(select(Transaction).where(Transaction.id == transaction_id))
        ).scalar_one()
        await create_notification(
            db,
            user_id=recipient,
            type="attribution_removed",
            title=f"{txn.raw_merchant_name} se quitó de tus gastos",
            payload={"transaction_id": str(transaction_id)},
        )
    return True
```

> Note: `create_notification` currently commits internally (and then `await db.refresh(notif)`). Inside these ops we want the caller (endpoint) to own the transaction boundary. In Step 3 add a `commit: bool = True` param to `create_notification` and pass `commit=False` here (avoids touching every caller). **When `commit=False`, skip both the `await db.commit()` and the `await db.refresh(notif)`** (refresh after only a flush is unnecessary and can error) — instead `await db.flush()` so the row gets its id. Verify existing callers (which keep `commit=True`) still pass.

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && uv run pytest tests/test_transaction_attribution.py -v`
Expected: all PASS.

- [ ] **Step 5: Lint & commit**

```bash
cd backend && uv run ruff check modules/transactions/attribution.py modules/notifications/service.py tests/test_transaction_attribution.py && uv run ruff format modules/transactions/attribution.py modules/notifications/service.py tests/test_transaction_attribution.py
cd .. && git add backend/modules/transactions/attribution.py backend/modules/notifications/service.py backend/tests/test_transaction_attribution.py
git commit --no-verify -m "feat(attribution): hand-off (upsert), reject, un-tag, resolve recipient

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01KTzzogYq2HwKtDuvJttYFa"
```

---

### Task 4: Recipient inclusion in the caller's queries (exactly-one-owner)

**Files:**
- Modify: `backend/modules/transactions/service.py` (`get_my_transactions`, `get_dashboard_summary`)
- Modify: `backend/modules/budgets/v2_queries.py` (personal-view predicate, ~lines 239/308/403)
- Test: `backend/tests/test_transaction_attribution.py`

- [ ] **Step 1: Write failing test** (append)

```python
async def test_exactly_one_owner_in_dashboard(db):
    from modules.transactions.attribution import hand_off
    from modules.transactions.service import get_dashboard_summary, get_my_transactions

    rafael, camila, hh = await _couple(db)
    txn = await _charge(db, rafael, hh, amount="-40.00")
    db.add(TransactionSplit(transaction_id=txn.id, split_type="personal"))
    await db.flush()
    await hand_off(db, txn, sender_id=rafael.id, recipient_id=camila.id)
    await db.flush()

    month = datetime.now(timezone.utc).strftime("%Y-%m")
    r_sum = await get_dashboard_summary(db, rafael.id, month, "USD")
    c_sum = await get_dashboard_summary(db, camila.id, month, "USD")
    assert r_sum["expenses"] == 0, "handed-off charge must leave Rafael's totals"
    assert c_sum["expenses"] != 0, "handed-off charge must count for Camila"

    # Visible in Rafael's list (labeled), and in Camila's list.
    r_list = await get_my_transactions(db, rafael.id, since=txn.transaction_date.date())
    c_list = await get_my_transactions(db, camila.id, since=txn.transaction_date.date())
    assert any(t["id"] == txn.id for t in r_list)
    assert any(t["id"] == txn.id for t in c_list)
```

- [ ] **Step 2: Run to verify fail**

Run: `cd backend && uv run pytest tests/test_transaction_attribution.py::test_exactly_one_owner_in_dashboard -v`
Expected: FAIL — Camila's `expenses == 0` (her queries don't include attributed rows yet) and she doesn't see it in her list.

- [ ] **Step 3: Implement**

In `get_dashboard_summary` (already `outerjoin`s `TransactionSplit`): replace the base owner condition `Transaction.user_id == user_id` with the attribution-aware predicate, and add the attribution outerjoin. Use `owned_by_caller_clause`:

```python
from modules.transactions.attribution import owned_by_caller_clause
from modules.transactions.models import TransactionAttribution

# in conds: drop `Transaction.user_id == user_id`; instead add owned_by_caller_clause(user_id)
# and add to BOTH the totals query and the category query:
#   .outerjoin(TransactionAttribution, TransactionAttribution.transaction_id == Transaction.id)
```
Keep the existing `split_type != 'partner'` exclusion? **No** — replace it. The attribution predicate now supersedes it: a caller's own row that is actively attributed away is excluded by `owned_by_caller_clause`; a row attributed to the caller is included even though its `split_type='partner'`. Removing the standalone partner exclusion here is required, or Camila's attributed (partner-split) rows would be filtered out. (Rafael still excludes his handed-off rows because they're attributed away.)
> Exclude-only partner rows (no attribution) with `Transaction.user_id == caller`: `owned_by_caller_clause` keeps them (not attributed away). To preserve today's "exclude-only counts for nobody" for account-level partner cards, keep a narrower guard: `AND NOT (split_type='partner' AND no active attribution)`. Implement as: `owned_by_caller_clause(user_id) AND NOT (TransactionSplit.split_type == 'partner' AND attributed_to_clause is false)`. Simplest correct form:
```python
from sqlalchemy import and_, not_
exclude_only_partner = and_(
    TransactionSplit.split_type == "partner",
    TransactionAttribution.id.is_(None),
)
conds = [
    owned_by_caller_clause(user_id),
    not_(exclude_only_partner),
    ...  # currency, dates, counts_toward_totals
]
```

**Each of the three call sites needs a DIFFERENT predicate — do NOT reuse `owned_by_caller_clause` everywhere.** `owned_by_caller_clause` is correct ONLY for the exactly-one-owner *aggregates* (dashboard totals + category). It deliberately excludes the caller's own rows that are attributed away — which is right for totals but wrong for the visible list and for the personal-budget filter. Add these two named builders to `attribution.py` (Task 2 file) and use the right one per site:

```python
# backend/modules/transactions/attribution.py — append
from sqlalchemy import and_, not_


def list_visible_clause(caller_id: uuid.UUID):
    """LIST views: the caller sees their OWN rows (even ones handed off — they
    stay visible, labeled) PLUS rows handed off TO them. No exclusion.
    Requires outerjoin(TransactionAttribution)."""
    return or_(Transaction.user_id == caller_id, attributed_to_clause(caller_id))


def personal_scope_clause(caller_id: uuid.UUID):
    """PERSONAL-budget view: the caller's own personal/untagged rows that are
    NOT attributed away, PLUS rows attributed to them. Excludes the caller's
    own SHARED rows (those belong to the household view) and exclude-only
    partner rows. Requires outerjoin(TransactionSplit) and
    outerjoin(TransactionAttribution)."""
    attributed_away = (TransactionAttribution.id.isnot(None)) & (
        TransactionAttribution.status == "active"
    )
    own_personal = and_(
        Transaction.user_id == caller_id,
        or_(TransactionSplit.split_type == "personal", TransactionSplit.split_type.is_(None)),
        not_(attributed_away),
    )
    return or_(own_personal, attributed_to_clause(caller_id))
```

Then wire per site (each must add `.outerjoin(TransactionAttribution, TransactionAttribution.transaction_id == Transaction.id)`):

- **`get_dashboard_summary`** (aggregate) — use `owned_by_caller_clause(user_id)` + `not_(exclude_only_partner)` as written above. ✅ (already correct)
- **`get_my_transactions`** (list) — replace `Transaction.user_id == user_id` with `list_visible_clause(user_id)`. This keeps Rafael's handed-off charge visible (satisfies the Task 4 Step 1 assertion `any(t["id"] == txn.id for t in r_list)`) and shows Camila her attributed rows. Do NOT add the `exclude_only_partner` guard here.
- **`budgets/v2_queries.py`** personal-view queries (~lines 232/239, 301/308, 396/403) — replace BOTH the `Transaction.user_id == user_id` clause AND the `(split_type=='personal') | (split_type.is_(None))` clause with the single `personal_scope_clause(user_id)`, and add the `TransactionAttribution` outerjoin to all three queries. Removing the standalone `user_id` clause is required — otherwise Camila's attributed rows (whose `Transaction.user_id` is Rafael's) are filtered out.

- [ ] **Step 3b: Add a budgets-leak regression test** — assert the caller's own `shared` row does NOT appear in their personal budget after the swap (guards the `personal_scope_clause` against the "shared leaks into personal" failure). Put it in `tests/test_transaction_attribution.py` or the existing budgets test module if one exists.

- [ ] **Step 4: Run to verify pass** (and no regressions)

Run: `cd backend && uv run pytest tests/test_transaction_attribution.py tests/test_joint_account_split_default.py tests/test_merchant_review_approve_split_type.py -v`
Expected: all PASS. Also run any existing budgets test module (`ls tests | grep budget`) and confirm green.

- [ ] **Step 5: Lint & commit**

```bash
cd backend && uv run ruff check modules/transactions/service.py modules/budgets/v2_queries.py && uv run ruff format modules/transactions/service.py modules/budgets/v2_queries.py
cd .. && git add backend/modules/transactions/service.py backend/modules/budgets/v2_queries.py backend/tests/test_transaction_attribution.py
git commit --no-verify -m "feat(attribution): include attributed charges in recipient's totals/list/budgets

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01KTzzogYq2HwKtDuvJttYFa"
```

---

### Task 5: Endpoints — attribute / reject / un-attribute

**Files:**
- Modify: `backend/modules/transactions/router.py`
- Test: `backend/tests/test_transaction_attribution.py` (endpoint-level, via the app's auth dependency override used by other route tests — mirror `tests/test_bank_accounts_routes.py`)

Endpoints:
- `POST /transactions/{transaction_id}/attribute` body `{recipient_id?: uuid}` — caller must own the txn (or be an active member of its household); resolves recipient if omitted. **When `recipient_id` is passed explicitly, validate it is an active co-member of the txn's household** (spec §Data model requires both users be active members at write time) — return `422 {"detail":"recipient_not_in_household"}` otherwise; `resolve_recipient` already enforces this on the auto path. On `AmbiguousRecipient` returns `409 {"detail":"ambiguous_recipient","candidates":[...]}`; on no recipient returns `422 {"detail":"no_partner_in_household"}`. Calls `hand_off`, commits.
- `POST /attributions/{attribution_id}/reject` — recipient only; calls `reject`; `404` if not found / not theirs.
- `POST /attributions/{attribution_id}/acknowledge` — recipient only; sets `acknowledged_at`.
- `DELETE /transactions/{transaction_id}/attribute` — sender only; calls `un_tag`.

- [ ] **Step 1: Write failing test** — POST attribute with implicit recipient returns 200 and creates the attribution; wrong user rejecting returns 404. (Follow the auth-override pattern in `tests/test_bank_accounts_routes.py`.)
- [ ] **Step 2: Run to verify fail** (`404`/route missing).
- [ ] **Step 3: Implement the four routes**, delegating to `modules.transactions.attribution`. Wrap `AmbiguousRecipient` → `HTTPException(409, ...)`. Commit at the end of each handler.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Lint & commit** (`feat(attribution): attribute/reject/acknowledge/un-attribute endpoints`).

---

### Task 6: Leave-household revert hook

**Files:**
- Modify: `backend/modules/households/service.py` (the member-leave path that sets `left_at`)
- Test: `backend/tests/test_transaction_attribution.py`

- [ ] **Step 1: Write failing test** — Camila has an active attribution; she leaves the household (`left_at` set via the leave path); assert her attributions are `rejected`/removed and the split reverted to `personal` on Rafael's rows.
- [ ] **Step 2: Run to verify fail.**
- [ ] **Step 3: Implement** — in the leave path, for every `active` attribution where `attributed_to_user_id == leaving_user`, set `status='rejected'` and revert the txn's split to `personal`. Reuse `_set_split` (export it or add a small helper `revert_attributions_for_member(db, user_id)` in `attribution.py`).
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Lint & commit.**

---

### Task 7: Frontend — split editor triggers hand-off + API

**Files:**
- Modify: `frontend/app/lib/api.ts`
- Modify: `frontend/app/(dashboard)/components/SplitTypeEditor.tsx`

- [ ] **Step 1: Add API methods & types** — `attributeTransaction(txnId, recipientId?)`, `rejectAttribution(attrId)`, `acknowledgeAttribution(attrId)`, `unattributeTransaction(txnId)`; extend the notification payload type with `transaction_id, attribution_id, merchant, amount, currency`.
- [ ] **Step 2: Wire SplitTypeEditor** — when the user picks **De mi pareja**: instead of `updateTransactionSplitType(txn.id, "partner")`, call `attributeTransaction(txn.id)`. On `409 ambiguous_recipient`, show a small chooser of candidates (couples case never hits this). On `422 no_partner_in_household`, fall back to `updateTransactionSplitType(txn.id, "partner")` (exclude-only). On success invalidate `["transactions"]`, `["dashboard-summary"]`, `["notifications"]`. Picking Personal/Compartido keeps calling `updateTransactionSplitType`; switching *away* from De mi pareja on an attributed row calls `unattributeTransaction`.
- [ ] **Step 3: Typecheck** — `cd frontend && npx tsc --noEmit` → no errors.
- [ ] **Step 4: Commit.**

---

### Task 8: Frontend — notification rendering & actions

**Files:**
- Modify: `frontend/app/(dashboard)/notifications/page.tsx`

- [ ] **Step 1: Add icon + detail + actions** — `charge_attributed`: CreditCard icon, detail line `merchant · amount`, buttons **Confirmar** (→ `acknowledgeAttribution`) / **No es mío** (→ `rejectAttribution`); both mark the notification actioned and invalidate `["notifications"]`, `["transactions"]`, `["dashboard-summary"]`. `attribution_rejected` and `attribution_removed`: informational (icon + detail, no buttons). Mirror the existing `new_account_detected` block.
- [ ] **Step 2: Typecheck** — `npx tsc --noEmit`.
- [ ] **Step 3: Verify end-to-end** with `/browser-use` (login `rafaellabra96@gmail.com`): tag a charge De mi pareja → it leaves the dashboard total, stays listed labeled; a `charge_attributed` notification exists. (Recipient-side view requires Camila's login — note as manual check.)
- [ ] **Step 4: Commit.**

---

### Task 9: Phase-1 verification pass

- [ ] Run the full attribution suite + adjacent suites: `cd backend && uv run pytest tests/test_transaction_attribution.py tests/test_joint_account_split_default.py tests/test_bank_accounts_routes.py tests/test_merchant_review_approve_split_type.py -q`. Expected: all pass.
- [ ] `cd frontend && npx tsc --noEmit` clean.
- [ ] Confirm exactly-one-owner by re-reading the predicate: no path counts a row for both users; no path counts an attributed row for nobody.
- [ ] Update `ARCHITECTURE.md` (data model + endpoints) and `NEXT-STEPS.md` (mark Phase 2 pending). Commit.

---

# PHASE 2 — Per-person card balance view

### Task 10: `account_person_balances` service

**Files:**
- Modify: `backend/modules/transactions/attribution.py`
- Test: `backend/tests/test_account_person_balances.py`

- [ ] **Step 1: Write failing test** — on a bank account with Rafael's charges+payments and Camila's attributed charges+payments, assert `account_person_balances` returns per effective-owner `{gastos, pagos, saldo}` with `saldo = gastos - pagos`, amounts in the account currency's minor units.
- [ ] **Step 2: Run to verify fail.**
- [ ] **Step 3: Implement** — query the account's transactions, `outerjoin(TransactionAttribution)`, group by `effective_owner_id`; `gastos = Σ abs(amount) where amount<0`; `pagos = Σ amount where amount>0` (payments/credits); `saldo = gastos - pagos`. Return a list of `{user_id, name, gastos, pagos, saldo}`.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Lint & commit.**

### Task 11: Expose + render the balance view

**Files:**
- Modify: `backend/modules/bank_accounts/router.py` (add `GET /bank-accounts/{id}/person-balances`, owner-only)
- Modify: `frontend/app/(dashboard)/settings/components/BankAccountsSection.tsx`
- Modify: `frontend/app/lib/api.ts`

- [ ] **Step 1 (backend):** route test → implement route → pass → commit.
- [ ] **Step 2 (frontend):** on a detected/Plaid card that has ≥1 attribution, fetch and render the per-person block (`gastos · pagos · saldo` per person), styled like the existing account rows. Only shown to the account owner.
- [ ] **Step 3:** `npx tsc --noEmit`; `/browser-use` visual check.
- [ ] **Step 4:** Commit.

### Task 12: Final verification & docs

- [ ] Full suite green; typecheck clean.
- [ ] `/browser-use` end-to-end: tag a charge and a payment as Camila's → per-person balance shows her `gastos`, `pagos`, `saldo`.
- [ ] Update `README.md` (feature list), `ARCHITECTURE.md`, `NEXT-STEPS.md`. Commit.

---

## Notes for the implementer
- **Production DB caution:** local `.env` `DATABASE_URL` is PROD. Only Task 1's migration changes schema (new empty table — safe). Confirm before `alembic upgrade head`. Do not run destructive/data migrations without user sign-off.
- **`create_notification` commit boundary:** Task 3 changes it to not force a commit inside the ops (add `commit: bool = True`, pass `commit=False` from attribution ops; endpoints own the commit). Verify all existing callers keep their commit.
- **Exactly-one-owner is the load-bearing invariant.** The one predicate (`owned_by_caller_clause` + the `not_(exclude_only_partner)` guard on aggregates) is the only thing standing between correct books and double-counting. Any new aggregate over `transactions` must reuse it.
- **Reuse, don't re-derive:** amounts via `modules/currencies/units.py`; totals exclusion via `modules/transactions/totals.py`; split edits via `mark_user_edited`.
</content>
