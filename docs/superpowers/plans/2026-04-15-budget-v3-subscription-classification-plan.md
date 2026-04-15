# Budget v3 — Subscription Classification Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit per-subscription `Personal` / `Compartido` classification toggle to the subscriptions detail table. Store the override on `subscription_overrides`. When the user toggles, cascade the new split_type to the last 3 months of underlying `transaction_splits` rows (update existing, insert missing). Update the household known-bills query to filter by effective `split_type='shared'` and add a new personal filter helper, so the v3 Sankey can trust the hogar vs personal buckets.

**Architecture:** Additive migration 036 adds `subscription_overrides.split_type`. A new service method `reclassify_subscription_split` handles the cascade + cache invalidation atomically. Read helpers filter by effective split_type (override wins over inferred). Frontend gains one column + click-to-flip pill that calls the existing `PUT /subscriptions/override` endpoint (extended to accept `split_type`). This plan is the **prerequisite PR** that must merge before the v3 Sankey redesign plan can start.

**Tech Stack:** FastAPI + SQLAlchemy async + Alembic (backend), Next.js 14 + React Query (frontend), pytest (tests).

**Spec reference:** `docs/superpowers/specs/2026-04-15-budget-v3-sankey-redesign-design.md` §5.

---

## File Structure

**Files to create:**
- `backend/alembic/versions/036_subscription_overrides_split_type.py` — migration
- `backend/tests/test_subscription_reclassify.py` — cascade + override + read-filter tests

**Files to modify:**
- `backend/modules/subscriptions/schemas.py` — extend `SubscriptionOverrideRequest` with optional `split_type` field
- `backend/modules/subscriptions/service.py` — extend `upsert_override` signature; add `reclassify_subscription_split`; extend `_merge_overrides` to apply override `split_type`; extend `_compute_summary_by_currency` stays untouched (summary is currency-wide)
- `backend/modules/subscriptions/read.py` — `get_household_known_bills` filters effective `split_type='shared'`; new `get_user_personal_known_bills(user_id, currency)`
- `backend/modules/subscriptions/router.py` — `PUT /subscriptions/override` passes new `split_type` through to service
- `frontend/app/(dashboard)/subscriptions/page.tsx` — add `Clasificación` column (grid template change from 5 to 6 cols), click-to-flip pill component, wire to existing `useSubscriptionOverride` mutation with `split_type` field

**Files NOT touched (but worth being aware of):**
- `backend/modules/budgets/v2_service.py` — the budget-v2 code path consumes `read.py` helpers; no direct changes here. The v3 Sankey plan does the v2_service work.
- `frontend/app/lib/hooks/useSubscriptions.ts` — uses the existing mutation; we extend its payload shape to carry `split_type`. May need a minor type update.

---

## Task 1: Alembic migration 036

**Files:**
- Create: `backend/alembic/versions/036_subscription_overrides_split_type.py`
- Test: inline via `alembic upgrade/downgrade` commands

- [ ] **Step 1: Create the migration file**

Create `backend/alembic/versions/036_subscription_overrides_split_type.py`:

```python
"""036 — add subscription_overrides.split_type

Revision ID: 036
Revises: 035
"""

import sqlalchemy as sa
from alembic import op

revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscription_overrides",
        sa.Column("split_type", sa.String(), nullable=True),
    )
    op.create_check_constraint(
        "ck_subscription_overrides_split_type",
        "subscription_overrides",
        "split_type IS NULL OR split_type IN ('personal', 'shared')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_subscription_overrides_split_type",
        "subscription_overrides",
        type_="check",
    )
    op.drop_column("subscription_overrides", "split_type")
```

- [ ] **Step 2: Run the upgrade**

Run: `cd backend && .venv/bin/alembic upgrade head`

Expected: `INFO  [alembic.runtime.migration] Running upgrade 035 -> 036, 036 — add subscription_overrides.split_type`

- [ ] **Step 3: Verify the column and constraint exist**

Run: `cd backend && .venv/bin/python -c "from sqlalchemy import create_engine, inspect; import os; e = create_engine(os.environ['DATABASE_URL'].replace('+asyncpg','')); i = inspect(e); print([c['name'] for c in i.get_columns('subscription_overrides')])"`

Expected: list includes `'split_type'`.

- [ ] **Step 4: Verify downgrade works**

Run: `cd backend && .venv/bin/alembic downgrade -1 && .venv/bin/alembic upgrade head`

Expected: Downgrade and re-upgrade succeed without errors.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/036_subscription_overrides_split_type.py
git commit -m "feat(subs): migration 036 — add subscription_overrides.split_type"
git push origin main
```

---

## Task 2: Extend `SubscriptionOverrideRequest` schema

**Files:**
- Modify: `backend/modules/subscriptions/schemas.py` — add `split_type` field
- Test: `backend/tests/test_subscription_reclassify.py` — schema validation test

- [ ] **Step 1: Write the failing schema test**

Create `backend/tests/test_subscription_reclassify.py` (new file, will grow across tasks):

```python
"""Tests for subscription split_type classification and cascade behavior."""
from __future__ import annotations

import pytest

from modules.subscriptions.schemas import SubscriptionOverrideRequest


class TestSubscriptionOverrideRequestSchema:
    def test_accepts_optional_split_type_shared(self):
        req = SubscriptionOverrideRequest(merchant_key="netflix", split_type="shared")
        assert req.split_type == "shared"

    def test_accepts_optional_split_type_personal(self):
        req = SubscriptionOverrideRequest(merchant_key="netflix", split_type="personal")
        assert req.split_type == "personal"

    def test_split_type_defaults_to_none(self):
        req = SubscriptionOverrideRequest(merchant_key="netflix")
        assert req.split_type is None

    def test_rejects_invalid_split_type(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SubscriptionOverrideRequest(merchant_key="netflix", split_type="partner")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_subscription_reclassify.py::TestSubscriptionOverrideRequestSchema -v`

Expected: FAIL — `split_type` field doesn't exist on `SubscriptionOverrideRequest`.

- [ ] **Step 3: Add the field to the schema**

Edit `backend/modules/subscriptions/schemas.py` — modify the existing `SubscriptionOverrideRequest` class:

```python
from typing import Literal


class SubscriptionOverrideRequest(BaseModel):
    merchant_key: str
    status: str | None = None
    category: str | None = None
    next_charge_day: int | None = None
    split_type: Literal["personal", "shared"] | None = None
```

- [ ] **Step 4: Re-run the test**

Run: `cd backend && .venv/bin/pytest tests/test_subscription_reclassify.py::TestSubscriptionOverrideRequestSchema -v`

Expected: PASS — all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/subscriptions/schemas.py backend/tests/test_subscription_reclassify.py
git commit -m "feat(subs): add split_type field to SubscriptionOverrideRequest"
git push origin main
```

---

## Task 3: Extend `upsert_override` service to persist `split_type`

**Files:**
- Modify: `backend/modules/subscriptions/service.py:167-195` — extend `upsert_override` signature and SQL
- Test: `backend/tests/test_subscription_reclassify.py` — persistence test

- [ ] **Step 1: Write the failing service test**

Append to `backend/tests/test_subscription_reclassify.py`:

```python
from uuid import uuid4

from sqlalchemy import text

from modules.subscriptions.service import upsert_override


class TestUpsertOverrideSplitType:
    @pytest.mark.asyncio
    async def test_upsert_persists_split_type(self, async_session, seed_user):
        user_id = seed_user.id
        await upsert_override(
            async_session,
            user_id=user_id,
            merchant_key="netflix",
            status=None,
            category=None,
            next_charge_day=None,
            split_type="shared",
        )
        row = await async_session.execute(
            text("SELECT split_type FROM subscription_overrides "
                 "WHERE user_id = :uid AND merchant_key = 'netflix'"),
            {"uid": str(user_id)},
        )
        assert row.scalar() == "shared"

    @pytest.mark.asyncio
    async def test_upsert_update_changes_split_type(self, async_session, seed_user):
        user_id = seed_user.id
        await upsert_override(
            async_session, user_id=user_id, merchant_key="netflix",
            status=None, category=None, next_charge_day=None, split_type="personal",
        )
        await upsert_override(
            async_session, user_id=user_id, merchant_key="netflix",
            status=None, category=None, next_charge_day=None, split_type="shared",
        )
        row = await async_session.execute(
            text("SELECT split_type FROM subscription_overrides "
                 "WHERE user_id = :uid AND merchant_key = 'netflix'"),
            {"uid": str(user_id)},
        )
        assert row.scalar() == "shared"

    @pytest.mark.asyncio
    async def test_upsert_without_split_type_leaves_existing(self, async_session, seed_user):
        user_id = seed_user.id
        await upsert_override(
            async_session, user_id=user_id, merchant_key="netflix",
            status=None, category=None, next_charge_day=None, split_type="shared",
        )
        await upsert_override(
            async_session, user_id=user_id, merchant_key="netflix",
            status="active", category="Entretenimiento", next_charge_day=None,
            split_type=None,
        )
        row = await async_session.execute(
            text("SELECT split_type, status, category FROM subscription_overrides "
                 "WHERE user_id = :uid AND merchant_key = 'netflix'"),
            {"uid": str(user_id)},
        )
        got = row.one()
        assert got.split_type == "shared"  # preserved, NOT overwritten to NULL
        assert got.status == "active"
        assert got.category == "Entretenimiento"
```

- [ ] **Step 2: Check the existing test fixtures for `seed_user`**

Run: `cd backend && grep -r "def seed_user" tests/conftest.py tests/fixtures/ 2>/dev/null || grep -rn "seed_user\|async_session" tests/conftest.py 2>/dev/null | head -20`

Expected: find how `async_session` and a user fixture are spun up in existing tests. If there's no `seed_user` fixture, adapt the test to use whatever fixture pattern the existing test files use (typically `async_session` + `User` row insert via the ORM). Look at `tests/test_subscriptions_read.py` for a working example of the existing fixtures.

- [ ] **Step 3: Run the failing tests**

Run: `cd backend && .venv/bin/pytest tests/test_subscription_reclassify.py::TestUpsertOverrideSplitType -v`

Expected: FAIL — `upsert_override()` does not accept the `split_type` kwarg.

- [ ] **Step 4: Extend `upsert_override` in `service.py`**

Edit `backend/modules/subscriptions/service.py` — modify `upsert_override`:

```python
async def upsert_override(
    db: AsyncSession,
    user_id,
    merchant_key: str,
    status: str | None,
    category: str | None,
    next_charge_day: int | None,
    split_type: str | None = None,
) -> None:
    """Create or update a subscription override."""
    await db.execute(
        text("""
            INSERT INTO subscription_overrides (
                user_id, merchant_key, status, category, next_charge_day, split_type, updated_at
            )
            VALUES (:uid, :mk, COALESCE(:status, 'active'), :cat, :day, :split_type, NOW())
            ON CONFLICT (user_id, merchant_key)
            DO UPDATE SET
                status = COALESCE(:status, subscription_overrides.status),
                category = CASE WHEN :cat IS NOT NULL THEN :cat ELSE subscription_overrides.category END,
                next_charge_day = CASE WHEN :day IS NOT NULL THEN :day ELSE subscription_overrides.next_charge_day END,
                split_type = CASE WHEN :split_type IS NOT NULL THEN :split_type ELSE subscription_overrides.split_type END,
                updated_at = NOW()
        """),
        {
            "uid": str(user_id),
            "mk": merchant_key,
            "status": status,
            "cat": category,
            "day": next_charge_day,
            "split_type": split_type,
        },
    )
    await db.commit()
```

Key change: `split_type` is added as a 7th parameter (kwarg, default `None`) and threaded into both the INSERT and the ON CONFLICT UPDATE with the same `CASE WHEN NOT NULL` guard used by `category` and `next_charge_day`, so a call with `split_type=None` never overwrites an existing value.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_subscription_reclassify.py::TestUpsertOverrideSplitType -v`

Expected: PASS — all 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/modules/subscriptions/service.py backend/tests/test_subscription_reclassify.py
git commit -m "feat(subs): extend upsert_override to persist split_type override"
git push origin main
```

---

## Task 4: Implement `reclassify_subscription_split` service (cascade + invalidate cache)

**Files:**
- Modify: `backend/modules/subscriptions/service.py` — add new function
- Test: `backend/tests/test_subscription_reclassify.py` — cascade tests

- [ ] **Step 1: Write the failing cascade tests**

Append to `backend/tests/test_subscription_reclassify.py`:

```python
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from modules.subscriptions.service import reclassify_subscription_split
from modules.transactions.models import Transaction, TransactionSplit


class TestReclassifySubscriptionSplit:
    @pytest.mark.asyncio
    async def test_cascade_updates_last_3_months_only(
        self, async_session, seed_user, seed_household
    ):
        """5 months of Netflix txns; reclassify; verify only last 3 months'
        transaction_splits are updated."""
        user_id = seed_user.id
        now = datetime.now(timezone.utc)

        # Create 5 months of Netflix transactions, one per month, with
        # existing transaction_splits rows defaulted to 'personal'
        tx_ids = []
        for months_ago in range(5):
            tx = Transaction(
                user_id=user_id,
                household_id=seed_household.id,
                raw_merchant_name="Netflix",
                amount=Decimal("-9.99"),
                currency="USD",
                transaction_date=now - timedelta(days=30 * months_ago),
                source="email",
                transaction_type="expense",
                category="Entretenimiento",
            )
            async_session.add(tx)
            await async_session.flush()
            split = TransactionSplit(
                transaction_id=tx.id,
                split_type="personal",
                decided_by_user_id=user_id,
            )
            async_session.add(split)
            tx_ids.append(tx.id)
        await async_session.commit()

        # Act: reclassify Netflix to 'shared'
        updated_count = await reclassify_subscription_split(
            async_session,
            user_id=user_id,
            merchant_key="Netflix",
            new_split_type="shared",
            window_months=3,
        )

        # Assert: only the 3 most recent txns got their split updated
        # (the two older ones are outside the 3-month window)
        assert updated_count == 3
        for i, tx_id in enumerate(tx_ids):
            row = await async_session.execute(
                text("SELECT split_type FROM transaction_splits WHERE transaction_id = :tid"),
                {"tid": str(tx_id)},
            )
            split_type = row.scalar()
            if i < 3:
                assert split_type == "shared", f"tx at month {i} should be shared"
            else:
                assert split_type == "personal", f"tx at month {i} should still be personal"

    @pytest.mark.asyncio
    async def test_cascade_inserts_missing_splits(
        self, async_session, seed_user, seed_household
    ):
        """Txns with no existing transaction_splits row get one inserted."""
        user_id = seed_user.id
        now = datetime.now(timezone.utc)
        tx = Transaction(
            user_id=user_id,
            household_id=seed_household.id,
            raw_merchant_name="Spotify",
            amount=Decimal("-7.55"),
            currency="USD",
            transaction_date=now - timedelta(days=10),
            source="email",
            transaction_type="expense",
            category="Entretenimiento",
        )
        async_session.add(tx)
        await async_session.commit()
        # No TransactionSplit row for this transaction

        count = await reclassify_subscription_split(
            async_session,
            user_id=user_id,
            merchant_key="Spotify",
            new_split_type="shared",
            window_months=3,
        )
        assert count == 1

        row = await async_session.execute(
            text("SELECT split_type, decided_by_user_id FROM transaction_splits "
                 "WHERE transaction_id = :tid"),
            {"tid": str(tx.id)},
        )
        got = row.one()
        assert got.split_type == "shared"
        assert str(got.decided_by_user_id) == str(user_id)

    @pytest.mark.asyncio
    async def test_cascade_persists_override_row(
        self, async_session, seed_user, seed_household
    ):
        user_id = seed_user.id
        await reclassify_subscription_split(
            async_session,
            user_id=user_id,
            merchant_key="Netflix",
            new_split_type="shared",
            window_months=3,
        )
        row = await async_session.execute(
            text("SELECT split_type FROM subscription_overrides "
                 "WHERE user_id = :uid AND merchant_key = 'Netflix'"),
            {"uid": str(user_id)},
        )
        assert row.scalar() == "shared"

    @pytest.mark.asyncio
    async def test_cascade_invalidates_cache(
        self, async_session, seed_user, seed_household
    ):
        user_id = seed_user.id
        # Prime the cache with an arbitrary result
        await async_session.execute(
            text("""
                INSERT INTO detected_subscriptions_cache (user_id, result_json, computed_at)
                VALUES (:uid, CAST('[]' AS jsonb), NOW())
                ON CONFLICT (user_id) DO UPDATE
                SET result_json = CAST('[]' AS jsonb), computed_at = NOW()
            """),
            {"uid": str(user_id)},
        )
        await async_session.commit()

        await reclassify_subscription_split(
            async_session,
            user_id=user_id,
            merchant_key="Netflix",
            new_split_type="shared",
            window_months=3,
        )
        row = await async_session.execute(
            text("SELECT COUNT(*) FROM detected_subscriptions_cache WHERE user_id = :uid"),
            {"uid": str(user_id)},
        )
        assert row.scalar() == 0  # cache row deleted

    @pytest.mark.asyncio
    async def test_rejects_invalid_split_type(
        self, async_session, seed_user, seed_household
    ):
        with pytest.raises(ValueError):
            await reclassify_subscription_split(
                async_session,
                user_id=seed_user.id,
                merchant_key="Netflix",
                new_split_type="bogus",
                window_months=3,
            )
```

- [ ] **Step 2: Run the failing tests**

Run: `cd backend && .venv/bin/pytest tests/test_subscription_reclassify.py::TestReclassifySubscriptionSplit -v`

Expected: FAIL — `reclassify_subscription_split` doesn't exist.

- [ ] **Step 3: Implement `reclassify_subscription_split` in `service.py`**

Append to `backend/modules/subscriptions/service.py`:

```python
async def reclassify_subscription_split(
    db: AsyncSession,
    user_id,
    merchant_key: str,
    new_split_type: str,
    window_months: int = 3,
) -> int:
    """Reclassify a subscription's split_type and cascade the change to the
    last `window_months` of underlying transaction_splits rows.

    Steps:
      1. Validate new_split_type in {'personal', 'shared'}
      2. Find all transactions for this user matching merchant_key (by
         normalized_name OR raw_merchant_name) with transaction_date within
         the cascade window
      3. For each tx: UPDATE transaction_splits.split_type if a row exists,
         else INSERT one
      4. Upsert subscription_overrides with the new split_type
      5. Invalidate detected_subscriptions_cache for this user

    Returns the count of transactions touched.
    """
    if new_split_type not in {"personal", "shared"}:
        raise ValueError(f"invalid split_type: {new_split_type!r}")

    # 2. Find candidate transactions in the window
    rows = await db.execute(
        text("""
            SELECT t.id
            FROM transactions t
            LEFT JOIN merchants m ON m.id = t.merchant_id
            WHERE t.user_id = :uid
              AND COALESCE(m.normalized_name, t.raw_merchant_name) = :mk
              AND t.transaction_date >= NOW() - (:months || ' months')::INTERVAL
        """),
        {"uid": str(user_id), "mk": merchant_key, "months": str(window_months)},
    )
    tx_ids = [r[0] for r in rows]

    affected = 0
    for tx_id in tx_ids:
        # Try update first
        upd = await db.execute(
            text("""
                UPDATE transaction_splits
                SET split_type = :new, decided_by_user_id = :uid, decided_at = NOW()
                WHERE transaction_id = :tid
            """),
            {"new": new_split_type, "uid": str(user_id), "tid": str(tx_id)},
        )
        if upd.rowcount == 0:
            # No existing split row — insert one
            await db.execute(
                text("""
                    INSERT INTO transaction_splits
                        (id, transaction_id, split_type, decided_by_user_id, decided_at, created_at)
                    VALUES
                        (gen_random_uuid(), :tid, :new, :uid, NOW(), NOW())
                """),
                {"tid": str(tx_id), "new": new_split_type, "uid": str(user_id)},
            )
        affected += 1

    # 4. Upsert the override row
    await db.execute(
        text("""
            INSERT INTO subscription_overrides
                (user_id, merchant_key, status, split_type, updated_at)
            VALUES (:uid, :mk, 'active', :new, NOW())
            ON CONFLICT (user_id, merchant_key)
            DO UPDATE SET split_type = :new, updated_at = NOW()
        """),
        {"uid": str(user_id), "mk": merchant_key, "new": new_split_type},
    )

    # 5. Invalidate the cache
    await db.execute(
        text("DELETE FROM detected_subscriptions_cache WHERE user_id = :uid"),
        {"uid": str(user_id)},
    )

    await db.commit()
    return affected
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_subscription_reclassify.py::TestReclassifySubscriptionSplit -v`

Expected: PASS — all 5 tests pass.

- [ ] **Step 5: Run the full test file to catch regressions**

Run: `cd backend && .venv/bin/pytest tests/test_subscription_reclassify.py -v`

Expected: PASS — all tests from Tasks 2, 3, and 4 pass.

- [ ] **Step 6: Commit**

```bash
git add backend/modules/subscriptions/service.py backend/tests/test_subscription_reclassify.py
git commit -m "feat(subs): reclassify_subscription_split with 3-month cascade"
git push origin main
```

---

## Task 5: Apply override `split_type` inside `_merge_overrides`

**Files:**
- Modify: `backend/modules/subscriptions/service.py:248-269` — extend `_merge_overrides`
- Test: `backend/tests/test_subscription_reclassify.py` — override wins test

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_subscription_reclassify.py`:

```python
from modules.subscriptions.service import get_detected_subscriptions


class TestOverrideWinsOverInferredSplitType:
    @pytest.mark.asyncio
    async def test_override_split_type_wins_over_inferred(
        self, async_session, seed_user, seed_household
    ):
        """When both an inferred split_type (from transaction_splits) and an
        override (from subscription_overrides.split_type) exist, the override
        value appears in the detected subscriptions payload."""
        user_id = seed_user.id
        now = datetime.now(timezone.utc)

        # Create 3 months of Netflix txns with transaction_splits='personal'
        for months_ago in range(3):
            tx = Transaction(
                user_id=user_id,
                household_id=seed_household.id,
                raw_merchant_name="Netflix",
                amount=Decimal("-9.99"),
                currency="USD",
                transaction_date=now - timedelta(days=30 * months_ago),
                source="email",
                transaction_type="expense",
                category="Entretenimiento",
            )
            async_session.add(tx)
            await async_session.flush()
            async_session.add(
                TransactionSplit(
                    transaction_id=tx.id,
                    split_type="personal",
                    decided_by_user_id=user_id,
                )
            )
        await async_session.commit()

        # Manually insert the override (simulating a separate user action
        # that didn't cascade through reclassify_subscription_split — this
        # path tests _merge_overrides in isolation)
        await async_session.execute(
            text("""
                INSERT INTO subscription_overrides
                    (user_id, merchant_key, status, split_type, updated_at)
                VALUES (:uid, 'Netflix', 'active', 'shared', NOW())
            """),
            {"uid": str(user_id)},
        )
        await async_session.commit()

        payload = await get_detected_subscriptions(async_session, user_id)
        netflix_items = [i for i in payload["items"] if i["merchant_name"] == "Netflix"]
        assert len(netflix_items) == 1
        assert netflix_items[0]["split_type"] == "shared"  # override won

    @pytest.mark.asyncio
    async def test_no_override_falls_back_to_inferred(
        self, async_session, seed_user, seed_household
    ):
        """When no override exists, the inferred split_type from
        transaction_splits wins."""
        user_id = seed_user.id
        now = datetime.now(timezone.utc)

        for months_ago in range(3):
            tx = Transaction(
                user_id=user_id,
                household_id=seed_household.id,
                raw_merchant_name="Spotify",
                amount=Decimal("-7.55"),
                currency="USD",
                transaction_date=now - timedelta(days=30 * months_ago),
                source="email",
                transaction_type="expense",
                category="Entretenimiento",
            )
            async_session.add(tx)
            await async_session.flush()
            async_session.add(
                TransactionSplit(
                    transaction_id=tx.id,
                    split_type="personal",
                    decided_by_user_id=user_id,
                )
            )
        await async_session.commit()

        payload = await get_detected_subscriptions(async_session, user_id)
        spotify_items = [i for i in payload["items"] if i["merchant_name"] == "Spotify"]
        assert len(spotify_items) == 1
        assert spotify_items[0]["split_type"] == "personal"
```

- [ ] **Step 2: Run the failing test**

Run: `cd backend && .venv/bin/pytest tests/test_subscription_reclassify.py::TestOverrideWinsOverInferredSplitType -v`

Expected: FAIL on `test_override_split_type_wins_over_inferred` — the override's `split_type` is not read or applied by `_merge_overrides`.

- [ ] **Step 3: Extend `_merge_overrides`**

Edit `backend/modules/subscriptions/service.py` — modify `_merge_overrides` to pull `split_type` from the overrides table and apply it:

```python
async def _merge_overrides(db: AsyncSession, user_id, raw_items: list[dict]) -> list[dict]:
    """Apply subscription_overrides on top of raw detected items."""
    result = await db.execute(
        text(
            "SELECT merchant_key, status, category, next_charge_day, split_type "
            "FROM subscription_overrides WHERE user_id = :uid"
        ),
        {"uid": str(user_id)},
    )
    overrides = {row.merchant_key: row for row in result.all()}

    merged = []
    for item in raw_items:
        item = dict(item)  # copy
        override = overrides.get(item["merchant_name"])
        if override:
            item["status"] = override.status
            if override.category:
                item["category"] = override.category
            if override.next_charge_day:
                item["next_charge_day"] = override.next_charge_day
            if override.split_type:
                item["split_type"] = override.split_type
        merged.append(item)
    return merged
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_subscription_reclassify.py::TestOverrideWinsOverInferredSplitType -v`

Expected: PASS — both tests pass.

- [ ] **Step 5: Run the full subscription test suite to catch regressions**

Run: `cd backend && .venv/bin/pytest tests/test_subscriptions_read.py tests/test_subscription_reclassify.py -v`

Expected: PASS — all existing + new tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/modules/subscriptions/service.py backend/tests/test_subscription_reclassify.py
git commit -m "feat(subs): _merge_overrides applies split_type override to detected items"
git push origin main
```

---

## Task 6: Filter household/personal known_bills by effective `split_type`

**Files:**
- Modify: `backend/modules/subscriptions/read.py` — filter `get_household_known_bills`, add `get_user_personal_known_bills`
- Test: `backend/tests/test_subscription_reclassify.py` — filter tests

- [ ] **Step 1: Write the failing read-filter tests**

Append to `backend/tests/test_subscription_reclassify.py`:

```python
from modules.subscriptions.read import (
    get_household_known_bills,
    get_user_personal_known_bills,
)


class TestKnownBillsFiltering:
    @pytest.mark.asyncio
    async def test_household_known_bills_excludes_personal_subs(
        self, async_session, seed_user, seed_household
    ):
        """A subscription tagged split_type='personal' must NOT count toward
        household known bills."""
        user_id = seed_user.id
        now = datetime.now(timezone.utc)

        # 3 months of a 'shared' bill: Comcast $56.20
        for m in range(3):
            tx = Transaction(
                user_id=user_id, household_id=seed_household.id,
                raw_merchant_name="Comcast", amount=Decimal("-56.20"),
                currency="USD",
                transaction_date=now - timedelta(days=30 * m),
                source="email", transaction_type="expense",
                category="Cuentas",
            )
            async_session.add(tx)
            await async_session.flush()
            async_session.add(TransactionSplit(
                transaction_id=tx.id, split_type="shared",
                decided_by_user_id=user_id,
            ))

        # 3 months of a 'personal' bill: Netflix $9.99
        for m in range(3):
            tx = Transaction(
                user_id=user_id, household_id=seed_household.id,
                raw_merchant_name="Netflix", amount=Decimal("-9.99"),
                currency="USD",
                transaction_date=now - timedelta(days=30 * m),
                source="email", transaction_type="expense",
                category="Entretenimiento",
            )
            async_session.add(tx)
            await async_session.flush()
            async_session.add(TransactionSplit(
                transaction_id=tx.id, split_type="personal",
                decided_by_user_id=user_id,
            ))
        await async_session.commit()

        household_total = await get_household_known_bills(
            async_session, seed_household.id, "USD"
        )
        personal_total = await get_user_personal_known_bills(
            async_session, user_id, "USD"
        )

        # Only Comcast should be in household total
        assert household_total == Decimal("56.20")
        # Only Netflix should be in personal total
        assert personal_total == Decimal("9.99")
```

- [ ] **Step 2: Run the failing test**

Run: `cd backend && .venv/bin/pytest tests/test_subscription_reclassify.py::TestKnownBillsFiltering -v`

Expected: FAIL — `get_user_personal_known_bills` doesn't exist, and `get_household_known_bills` currently returns both bills summed.

- [ ] **Step 3: Update `read.py`**

Edit `backend/modules/subscriptions/read.py` — replace the entire file:

```python
"""Household-scoped and personal-scoped `known_bills` readers for the budget endpoints.

The existing `modules.subscriptions.service.get_detected_subscriptions` is
strictly user-scoped. Budget-v2 / v3 need both a household-scoped and a
user-scoped sum, each filtered by effective `split_type`:

- Household known bills: subscriptions with effective `split_type='shared'`
- Personal known bills: subscriptions with effective `split_type='personal'`

"Effective" means: `subscription_overrides.split_type` if set, otherwise the
raw `split_type` from `detect_from_rows` (which reads it from
`transaction_splits.split_type` defaulting to 'personal').

This module does NOT filter by `contribution_mode` (that's `v2_service`'s job
when it constructs the household-level aggregate).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.households.models import HouseholdMember
from modules.subscriptions.service import get_detected_subscriptions


_ZERO = Decimal("0")


async def _sum_user_bills_by_split_type(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    wanted_split_type: str,
) -> Decimal:
    """Sum recurring bills for one user in `currency` where the effective
    split_type matches `wanted_split_type`."""
    payload = await get_detected_subscriptions(db, user_id)
    total = _ZERO
    for item in payload["items"]:
        if item.get("status") != "active":
            continue
        if item.get("currency") != currency:
            continue
        # split_type was already resolved by _merge_overrides — override wins
        # over inferred, so this read reflects the effective value.
        if item.get("split_type") == wanted_split_type:
            last = item.get("last_amount") or _ZERO
            total += last if isinstance(last, Decimal) else Decimal(str(last))
    return total


async def get_user_known_bills(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
) -> Decimal:
    """Sum the monthly total of ALL detected recurring bills for one user in
    `currency`, regardless of split_type. Used by the legacy v2 personal view
    entry points that don't yet discriminate between personal and shared."""
    payload = await get_detected_subscriptions(db, user_id)
    summary = payload.get("summary_by_currency") or {}
    curr_summary = summary.get(currency)
    if not curr_summary:
        return _ZERO
    total = curr_summary.get("total_recurring") or _ZERO
    return total if isinstance(total, Decimal) else Decimal(str(total))


async def get_user_personal_known_bills(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
) -> Decimal:
    """Sum of one user's recurring bills that are PERSONAL (not shared with
    the household). Used by the v3 personal view Sankey."""
    return await _sum_user_bills_by_split_type(db, user_id, currency, "personal")


async def get_household_known_bills(
    db: AsyncSession,
    household_id: uuid.UUID,
    currency: str,
) -> Decimal:
    """Sum of household SHARED recurring bills across every active member
    in `currency`. Active = `left_at IS NULL`. Only items whose effective
    split_type is 'shared' contribute — personal-tagged subs are excluded.

    The caller (`v2_service`) is responsible for adjusting the result based
    on contribution_mode — e.g. subtracting reimbursement members' bills,
    which don't hit the household pot.
    """
    member_rows = await db.execute(
        select(HouseholdMember.user_id).where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.left_at.is_(None),
        )
    )
    total = _ZERO
    for (user_id,) in member_rows:
        total += await _sum_user_bills_by_split_type(db, user_id, currency, "shared")
    return total
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_subscription_reclassify.py::TestKnownBillsFiltering -v`

Expected: PASS — both assertions hold.

- [ ] **Step 5: Run the full backend test suite to catch regressions**

Run: `cd backend && .venv/bin/pytest tests/test_budget_v2_endpoint.py tests/test_subscriptions_read.py tests/test_subscription_reclassify.py -v`

Expected: PASS — no regressions in existing v2 tests. **NOTE:** if `test_budget_v2_endpoint.py` uses fixtures where personal subs were previously counted as household known_bills, those tests may need their fixture adjustments to explicitly tag subs as `'shared'`. Investigate any failure and either (a) update the fixture to tag as shared, or (b) confirm the test was exercising the old (incorrect) behavior and update its assertions.

- [ ] **Step 6: Commit**

```bash
git add backend/modules/subscriptions/read.py backend/tests/test_subscription_reclassify.py
git commit -m "feat(subs): filter known_bills by effective split_type"
git push origin main
```

---

## Task 7: Router endpoint wiring

**Files:**
- Modify: `backend/modules/subscriptions/router.py` — pass `split_type` through
- Test: `backend/tests/test_subscription_reclassify.py` — HTTP integration test

- [ ] **Step 1: Write the failing HTTP test**

Append to `backend/tests/test_subscription_reclassify.py`:

```python
from httpx import AsyncClient


class TestClassifyEndpoint:
    @pytest.mark.asyncio
    async def test_put_override_with_split_type(
        self, authed_client: AsyncClient, seed_user, seed_household
    ):
        """PUT /subscriptions/override accepts split_type and cascades."""
        now = datetime.now(timezone.utc)
        # Seed a Netflix txn so reclassify has something to cascade over
        from core.database import async_session_maker
        async with async_session_maker() as db:
            tx = Transaction(
                user_id=seed_user.id, household_id=seed_household.id,
                raw_merchant_name="Netflix", amount=Decimal("-9.99"),
                currency="USD",
                transaction_date=now - timedelta(days=10),
                source="email", transaction_type="expense",
                category="Entretenimiento",
            )
            db.add(tx)
            await db.flush()
            db.add(TransactionSplit(
                transaction_id=tx.id, split_type="personal",
                decided_by_user_id=seed_user.id,
            ))
            await db.commit()

        resp = await authed_client.put(
            "/subscriptions/override",
            json={"merchant_key": "Netflix", "split_type": "shared"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # Verify the cascade happened
        async with async_session_maker() as db:
            row = await db.execute(
                text("""
                    SELECT ts.split_type
                    FROM transaction_splits ts
                    JOIN transactions t ON t.id = ts.transaction_id
                    WHERE t.user_id = :uid AND t.raw_merchant_name = 'Netflix'
                """),
                {"uid": str(seed_user.id)},
            )
            assert row.scalar() == "shared"
```

**NOTE:** the `authed_client` fixture comes from the existing test infrastructure — look at `tests/test_budget_v2_endpoint.py` or `tests/conftest.py` for the exact fixture name and how to get an authenticated HTTP client. If the fixture is named differently, adapt the import.

- [ ] **Step 2: Run the failing test**

Run: `cd backend && .venv/bin/pytest tests/test_subscription_reclassify.py::TestClassifyEndpoint -v`

Expected: FAIL — the router's `PUT /subscriptions/override` handler doesn't pass `split_type` to `upsert_override` or trigger the cascade.

- [ ] **Step 3: Update the router to call `reclassify_subscription_split`**

Edit `backend/modules/subscriptions/router.py` — replace the `upsert_override` handler:

```python
@router.put("/override")
async def upsert_override(
    body: SubscriptionOverrideRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # If the caller set split_type, go through the reclassify service so
    # the change cascades to the last 3 months of transaction_splits and
    # the detected_subscriptions_cache gets invalidated in one atomic
    # operation. reclassify also upserts the override row, so we don't
    # call upsert_override separately in that branch.
    if body.split_type is not None:
        await service.reclassify_subscription_split(
            db,
            user_id=current_user.id,
            merchant_key=body.merchant_key,
            new_split_type=body.split_type,
            window_months=3,
        )
        # If the request ALSO carries other override fields (status,
        # category, next_charge_day), apply them via upsert_override so
        # they don't get lost.
        if body.status is not None or body.category is not None or body.next_charge_day is not None:
            await service.upsert_override(
                db,
                current_user.id,
                body.merchant_key,
                body.status,
                body.category,
                body.next_charge_day,
                split_type=None,  # already applied above
            )
    else:
        await service.upsert_override(
            db,
            current_user.id,
            body.merchant_key,
            body.status,
            body.category,
            body.next_charge_day,
            split_type=None,
        )
    return {"ok": True}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_subscription_reclassify.py::TestClassifyEndpoint -v`

Expected: PASS.

- [ ] **Step 5: Run the full backend test suite**

Run: `cd backend && .venv/bin/pytest tests/ -x -q`

Expected: ALL tests pass (the existing 48 + the new cascade tests). If any regression, investigate and fix before proceeding.

- [ ] **Step 6: Commit**

```bash
git add backend/modules/subscriptions/router.py backend/tests/test_subscription_reclassify.py
git commit -m "feat(subs): PUT /override routes split_type through reclassify service"
git push origin main
```

---

## Task 8: Frontend — extend `useSubscriptionOverride` mutation payload

**Files:**
- Modify: `frontend/app/lib/hooks/useSubscriptions.ts` (or equivalent) — extend the mutation types and body
- Modify: `frontend/app/lib/api.ts` (or whichever module holds `api.subscriptions.override`) — extend the API function signature

- [ ] **Step 1: Locate the existing hook and API wrapper**

Run: `cd frontend && grep -rn "useSubscriptionOverride\b" app/ --include="*.ts" --include="*.tsx"`

Expected: find the definition file and every caller. Record the exact path — the plan references `frontend/app/lib/hooks/useSubscriptions.ts` but the actual location may be different. Use the real path going forward.

- [ ] **Step 2: Extend the mutation body type**

Edit the hook file. Find the mutation body interface (likely something like `SubscriptionOverridePayload` or inline `{ merchant_key, status?, category?, next_charge_day? }`) and add the optional field:

```ts
type SubscriptionOverridePayload = {
  merchant_key: string;
  status?: string | null;
  category?: string | null;
  next_charge_day?: number | null;
  split_type?: "personal" | "shared" | null;
};
```

- [ ] **Step 3: Extend the API client function**

Find `api.subscriptions.override` (or equivalent) in `frontend/app/lib/api.ts` (actual path TBD from Step 1). Extend the POST/PUT body to include `split_type` when provided:

```ts
async override(payload: SubscriptionOverridePayload) {
  const res = await fetch(`${API_URL}/subscriptions/override`, {
    method: "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to update override");
  return res.json();
}
```

(If the existing client uses a shared `fetch` wrapper, adapt to the actual pattern — do NOT introduce a new HTTP layer.)

- [ ] **Step 4: Verify `npm run build` is clean**

Run: `cd frontend && npm run build`

Expected: build succeeds with no TypeScript errors. If errors surface in callers that don't pass `split_type`, that's fine — the field is optional.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/lib/hooks/useSubscriptions.ts frontend/app/lib/api.ts
git commit -m "feat(frontend): subscription override payload accepts split_type"
git push origin main
```

---

## Task 9: Frontend — add `Clasificación` column with click-to-flip pill

**Files:**
- Modify: `frontend/app/(dashboard)/subscriptions/page.tsx:291-400` — add column to detail table

- [ ] **Step 1: Change the grid template to 6 columns**

Edit `frontend/app/(dashboard)/subscriptions/page.tsx` line 293 (table header grid) and line 326 (row grid):

```tsx
// HEADER
<div className="hidden sm:grid grid-cols-[2fr_1fr_1fr_1fr_1fr_60px] gap-2 px-4 py-2.5 bg-slate-50 border-b border-slate-200">
  <span className="text-[11px] font-semibold text-slate-400 uppercase">Servicio</span>
  <span className="text-[11px] font-semibold text-slate-400 uppercase">Monto</span>
  <span className="text-[11px] font-semibold text-slate-400 uppercase">Último cobro</span>
  <span className="text-[11px] font-semibold text-slate-400 uppercase">Categoría</span>
  <span className="text-[11px] font-semibold text-slate-400 uppercase">Clasificación</span>
  <span />
</div>
```

And the row grid (around line 326):

```tsx
<div
  className="grid grid-cols-[2fr_1fr_1fr_1fr_1fr_60px] gap-2 px-4 py-3 items-center cursor-pointer hover:bg-slate-50 transition-colors"
  onClick={() => setExpandedRow(isExpanded ? null : sub.merchant_name)}
>
```

- [ ] **Step 2: Add the classification pill cell between Categoría and Editar**

Still in `page.tsx`, after the Categoría span (around line 363) and before the `<button>Editar</button>` (around line 365), insert:

```tsx
<button
  onClick={(e) => {
    e.stopPropagation();
    const nextType = sub.split_type === "shared" ? "personal" : "shared";
    overrideMutation.mutate({
      merchant_key: sub.merchant_name,
      split_type: nextType,
    });
  }}
  disabled={overrideMutation.isPending}
  className={`text-[10px] font-semibold px-2 py-0.5 rounded-full text-center transition-colors disabled:opacity-50 ${
    sub.split_type === "shared"
      ? "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
      : "bg-blue-50 text-blue-700 hover:bg-blue-100"
  }`}
  title="Click para cambiar entre Personal y Compartido"
>
  {sub.split_type === "shared" ? "Compartido" : "Personal"}
</button>
```

The click handler:
- Stops propagation so the row expansion doesn't toggle
- Computes the flipped value
- Calls the existing `overrideMutation` with `merchant_key + split_type`
- Disables itself while pending to prevent double-click races
- Optimistically styles based on current `sub.split_type` (React Query will invalidate and refetch after the mutation resolves)

- [ ] **Step 3: Invalidate the budget query after the mutation resolves**

Find the `useSubscriptionOverride` mutation definition (from Task 8 Step 1). On `onSuccess`, invalidate both `subscriptions` and `budget` query keys so the budget page's Sankey reflects the new classification:

```ts
export function useSubscriptionOverride() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.subscriptions.override,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subscriptions"] });
      queryClient.invalidateQueries({ queryKey: ["budget"] });
    },
  });
}
```

(Only add the `budget` invalidation if it's not already there. If it is, skip this step.)

- [ ] **Step 4: Run the dev server and smoke-test manually**

Run (in separate terminals):

```bash
cd backend && .venv/bin/uvicorn main:app --reload --port 8000
cd frontend && npm run dev
```

Visit `http://localhost:3000/subscriptions`. Verify:
1. The detail table now has a `Clasificación` column
2. Each row shows a `Personal` (blue) or `Compartido` (green) pill
3. Clicking the pill flips the label AND persists across a page refresh
4. After a classification change, visiting `/budgets` shows the new classification reflected in `Gastos fijos` (if the v3 Sankey is also shipped — otherwise you'll just see the v2 total adjust)

- [ ] **Step 5: Verify `npm run build` is clean**

Run: `cd frontend && npm run build`

Expected: build succeeds.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/(dashboard)/subscriptions/page.tsx frontend/app/lib/hooks/useSubscriptions.ts
git commit -m "feat(frontend): subscription classification pill + click-to-flip"
git push origin main
```

---

## Task 10: Integration verification & merge gate

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend test suite**

Run: `cd backend && .venv/bin/pytest tests/ -q`

Expected: all tests pass. Count should be previous baseline (48) + all new tests from this plan. Note the new total for the PR description.

- [ ] **Step 2: Run the frontend build**

Run: `cd frontend && npm run build`

Expected: clean build with no TS errors or warnings.

- [ ] **Step 3: Check migration chain**

Run: `cd backend && .venv/bin/alembic history | head -20`

Expected: `036` is the head and it cleanly follows `035`.

- [ ] **Step 4: Smoke-test the endpoint against the real dev DB**

Run (with backend running):

```bash
curl -X PUT http://localhost:8000/subscriptions/override \
  -H "Content-Type: application/json" \
  -b "session=<your-session-cookie>" \
  -d '{"merchant_key": "TestMerchant", "split_type": "personal"}'
```

Expected: `{"ok": true}`. Then check the dev DB:

```sql
SELECT merchant_key, split_type FROM subscription_overrides
WHERE user_id = '<your-user-id>' AND merchant_key = 'TestMerchant';
```

Expected: row exists with `split_type = 'personal'`.

- [ ] **Step 5: Document the merge gate**

This plan's merge gate: **this PR must be merged to main before the v3 Sankey redesign plan (`2026-04-15-budget-v3-sankey-redesign-plan.md`) can start.** The Sankey plan depends on `get_household_known_bills` already filtering by `split_type='shared'` and on `get_user_personal_known_bills` being available.

No additional commit — this step is a human gate check.

---

## Self-Review (complete before handing off)

**Spec coverage** (§5 of the design doc):
- Migration 036 ✅ Task 1
- `reclassify_subscription_split` service ✅ Task 4
- `_merge_overrides` applies override split_type ✅ Task 5
- `get_household_known_bills` filters effective split_type ✅ Task 6
- `get_user_personal_known_bills` new helper ✅ Task 6
- Router endpoint extension ✅ Task 7
- Frontend `Clasificación` column + click-to-flip ✅ Task 9
- Cascade tests (3-month window, missing-split insert, override update, cache invalidation, invalid input rejection) ✅ Task 4
- Override wins over inferred ✅ Task 5
- Household/personal filter tests ✅ Task 6
- HTTP endpoint integration test ✅ Task 7
- Integration verification ✅ Task 10

**Placeholder scan:**
- Task 7 Step 1 notes that `authed_client` fixture name "may need adaptation" — this is a pointer, not a placeholder, because the exact fixture pattern varies across the repo and must be discovered on the fly. The step explicitly says where to look.
- Task 8 Step 1 has a grep command that locates the exact hook file path — because the plan references a canonical path but the real location must be confirmed. This is discovery, not a placeholder.
- No `TBD`, `TODO`, `implement later`, or generic "add appropriate error handling" patterns.

**Type consistency:**
- `reclassify_subscription_split(db, user_id, merchant_key, new_split_type, window_months=3)` signature is used identically in Task 4 definition and Task 7 router call.
- `SubscriptionOverridePayload` TypeScript type (Task 8) matches the `SubscriptionOverrideRequest` pydantic model (Task 2) — both have `merchant_key`, `status?`, `category?`, `next_charge_day?`, `split_type?` with the same literal union.
- `split_type: "personal" | "shared"` literal is consistent across backend (CHECK constraint, Literal type, service validation) and frontend (TS type, pill labels).

All good. Plan is ready to execute.
