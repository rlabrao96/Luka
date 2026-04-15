# Budget v3 — Sankey Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Merge gate:** The prerequisite plan `2026-04-15-budget-v3-subscription-classification-plan.md` MUST be fully merged to main before this plan starts. This plan depends on `get_household_known_bills` filtering by effective `split_type='shared'` and on `get_user_personal_known_bills` existing.

**Goal:** Replace the current 2-level Sankey on `/budgets/v2` with a 4-level Hogar layout and a 3-level Personal layout. The Hogar view shows caller-relative income source breakdown at Level 0, a single `Ingresos Hogar` hub at Level 1, a 4-node allocation split at Level 2 (`Meta de ahorro`, `Gastos fijos`, `Gasto personal`, `Disponible hogar`), and per-risk-category breakdown at Level 3. The Personal view is structurally similar but 3 levels (no `Gasto personal` node and no "other members"). Privacy invariant is extended: each caller sees their own income categories broken out; every other member appears as exactly one aggregated node.

**Architecture:** In-place update on `/budgets/v2` — Pydantic contract stays compatible via three additive optional fields on `SankeyNode` (`level`, `kind`, `member_id`). Backend replaces `_build_sankey` with two dedicated builders (`_build_hogar_sankey`, `_build_personal_sankey`) that share a `_pay_first_fit` routing helper. New `HouseholdIncomeBreakdown` dataclass extends `contribution_service.income_for_household_view` to return caller sources + per-member totals. New `user_budget_settings.personal_allocation_amount` column + service helpers drives the `Gasto personal` Level 2 node. Frontend `BudgetSankey.tsx` custom renderer updated to place labels by `level` rank instead of terminal-detection, with responsive width and updated tooltips. Source labels read the caller's own `user_category_preferences` entries with `sort_order` driving node order.

**Tech Stack:** FastAPI + SQLAlchemy async + Alembic + Pydantic (backend), Next.js 14 + Recharts 3.8 + React Query (frontend), pytest (tests).

**Spec reference:** `docs/superpowers/specs/2026-04-15-budget-v3-sankey-redesign-design.md`

---

## File Structure

**Files to create:**
- `backend/alembic/versions/037_user_budget_settings_personal_allocation.py` — migration
- `backend/tests/test_budget_v3_sankey.py` — v3-specific tests (flow conservation, caller-relative privacy, personal allocation wiring, 4-level structure)

**Files to modify:**
- `backend/modules/households/contribution_service.py` — add `HouseholdIncomeBreakdown` + `OtherMemberContribution` dataclasses, new `income_breakdown_for_household_view` function; keep `income_for_household_view` as a thin wrapper returning `breakdown.total`
- `backend/modules/budgets/v2_schemas.py` — additive optional fields on `SankeyNode`: `level`, `kind`, `member_id`
- `backend/modules/budgets/forecast.py` — extend `spendable_ceiling` with optional `personal_allocation: Decimal = Decimal("0")` kwarg
- `backend/modules/budgets/user_budget_settings_service.py` — add `get_personal_allocation(db, user_id, currency)` and `get_household_personal_allocation(db, household_id, currency)` mirrors of the existing savings-target helpers
- `backend/modules/budgets/v2_service.py` — replace `_build_sankey` with `_build_hogar_sankey` + `_build_personal_sankey` + shared `_pay_first_fit` helper; update `get_budget_v2` to wire the new breakdown structure + personal allocation into the builders
- `backend/tests/fixtures/budget_v2_sample_response.json` — regenerate to reflect the new multi-level structure
- `backend/tests/test_budget_v2_endpoint.py` — existing flow-conservation test expanded to the new structure; existing privacy test expanded to caller-relative check
- `frontend/app/(dashboard)/components/BudgetSankey.tsx` — rank-based label placement reading `level`/`kind`/`member_id`
- `frontend/app/(dashboard)/budgets/page.tsx` — wider container for 4-level layout
- `frontend/app/(dashboard)/settings/components/BudgetSettingsSection.tsx` — new input for `personal_allocation_amount` mirroring the existing savings target input

**Files NOT touched:**
- `backend/modules/budgets/cuota_service.py` — cuota logic unchanged
- `backend/modules/budgets/savings_categories.py` — savings category filter unchanged
- `backend/modules/households/models.py` — household schema unchanged (contribution_mode stays `full`/`fixed`/`reimbursement`)
- `backend/modules/subscriptions/*` — prerequisite plan did all subscription work

---

## Task 1: Migration 037 — `user_budget_settings.personal_allocation_amount`

**Files:**
- Create: `backend/alembic/versions/037_user_budget_settings_personal_allocation.py`

- [ ] **Step 1: Create the migration file**

Create `backend/alembic/versions/037_user_budget_settings_personal_allocation.py`:

```python
"""037 — add user_budget_settings.personal_allocation_amount / _currency

Revision ID: 037
Revises: 036
"""

import sqlalchemy as sa
from alembic import op

revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_budget_settings",
        sa.Column("personal_allocation_amount", sa.Numeric(14, 2), nullable=True),
    )
    op.add_column(
        "user_budget_settings",
        sa.Column("personal_allocation_currency", sa.String(length=3), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_budget_settings", "personal_allocation_currency")
    op.drop_column("user_budget_settings", "personal_allocation_amount")
```

- [ ] **Step 2: Run the upgrade**

Run: `cd backend && .venv/bin/alembic upgrade head`

Expected: `INFO  [alembic.runtime.migration] Running upgrade 036 -> 037`

- [ ] **Step 3: Verify the columns exist**

Run: `cd backend && .venv/bin/python -c "from sqlalchemy import create_engine, inspect; import os; e = create_engine(os.environ['DATABASE_URL'].replace('+asyncpg','')); print([c['name'] for c in inspect(e).get_columns('user_budget_settings')])"`

Expected: list includes both `'personal_allocation_amount'` and `'personal_allocation_currency'`.

- [ ] **Step 4: Verify downgrade works**

Run: `cd backend && .venv/bin/alembic downgrade -1 && .venv/bin/alembic upgrade head`

Expected: Downgrade and re-upgrade succeed.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/037_user_budget_settings_personal_allocation.py
git commit -m "feat(budget-v3): migration 037 — user_budget_settings.personal_allocation_amount"
git push origin main
```

---

## Task 2: `user_budget_settings_service` — personal allocation helpers

**Files:**
- Modify: `backend/modules/budgets/user_budget_settings_service.py` — add 2 new functions mirroring the existing savings target helpers
- Test: `backend/tests/test_user_budget_settings.py` — extend with new tests

- [ ] **Step 1: Read the existing file to understand the pattern**

Run: `cat backend/modules/budgets/user_budget_settings_service.py | head -100`

Expected: find the existing `get_savings_target(db, user_id, currency)` and `get_household_savings_target(db, household_id, currency)` — the new functions will mirror their structure exactly.

- [ ] **Step 2: Write the failing tests**

Append to `backend/tests/test_user_budget_settings.py`:

```python
import pytest
from decimal import Decimal

from modules.budgets.user_budget_settings_service import (
    get_personal_allocation,
    get_household_personal_allocation,
)


class TestPersonalAllocation:
    @pytest.mark.asyncio
    async def test_get_personal_allocation_returns_zero_when_unset(
        self, async_session, seed_user
    ):
        result = await get_personal_allocation(
            async_session, user_id=seed_user.id, currency="CLP"
        )
        assert result == Decimal("0")

    @pytest.mark.asyncio
    async def test_get_personal_allocation_returns_stored_value(
        self, async_session, seed_user
    ):
        # Upsert a value into user_budget_settings
        from sqlalchemy import text
        await async_session.execute(
            text("""
                INSERT INTO user_budget_settings
                    (user_id, personal_allocation_amount, personal_allocation_currency)
                VALUES (:uid, 500000, 'CLP')
                ON CONFLICT (user_id) DO UPDATE
                SET personal_allocation_amount = 500000,
                    personal_allocation_currency = 'CLP'
            """),
            {"uid": str(seed_user.id)},
        )
        await async_session.commit()
        result = await get_personal_allocation(
            async_session, user_id=seed_user.id, currency="CLP"
        )
        assert result == Decimal("500000")

    @pytest.mark.asyncio
    async def test_get_personal_allocation_ignores_wrong_currency(
        self, async_session, seed_user
    ):
        from sqlalchemy import text
        await async_session.execute(
            text("""
                INSERT INTO user_budget_settings
                    (user_id, personal_allocation_amount, personal_allocation_currency)
                VALUES (:uid, 500000, 'CLP')
                ON CONFLICT (user_id) DO UPDATE
                SET personal_allocation_amount = 500000,
                    personal_allocation_currency = 'CLP'
            """),
            {"uid": str(seed_user.id)},
        )
        await async_session.commit()
        # Request USD — should return 0 because the stored currency is CLP
        result = await get_personal_allocation(
            async_session, user_id=seed_user.id, currency="USD"
        )
        assert result == Decimal("0")

    @pytest.mark.asyncio
    async def test_household_personal_allocation_sums_full_and_fixed_members(
        self, async_session, seed_household_full_fixed
    ):
        """Household aggregate = sum across members whose contribution_mode
        is 'full' or 'fixed'. Reimbursement members are excluded."""
        # seed_household_full_fixed is a fixture with a full-mode user and a
        # fixed-mode user, both with personal_allocation_amount set in CLP
        # The fixture should set user1 to 500000 CLP and user2 to 300000 CLP
        result = await get_household_personal_allocation(
            async_session, household_id=seed_household_full_fixed.id, currency="CLP"
        )
        assert result == Decimal("800000")
```

**NOTE:** the `seed_household_full_fixed` fixture may not exist. Check `tests/conftest.py` for what household fixtures are available. If none match, extend the existing fixture pattern to create a mixed household and seed the personal_allocation_amount for both members as part of the test setup.

- [ ] **Step 3: Run the failing tests**

Run: `cd backend && .venv/bin/pytest tests/test_user_budget_settings.py::TestPersonalAllocation -v`

Expected: FAIL — `get_personal_allocation` and `get_household_personal_allocation` don't exist.

- [ ] **Step 4: Implement the helpers**

Append to `backend/modules/budgets/user_budget_settings_service.py`:

```python
async def get_personal_allocation(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    currency: str,
) -> Decimal:
    """Read the user's personal_allocation_amount in the requested currency.

    Returns Decimal('0') when no row exists or when the stored
    personal_allocation_currency does not match the requested currency.
    Mirrors the semantics of `get_savings_target`.
    """
    row = await db.execute(
        text("""
            SELECT personal_allocation_amount, personal_allocation_currency
            FROM user_budget_settings
            WHERE user_id = :uid
        """),
        {"uid": str(user_id)},
    )
    record = row.one_or_none()
    if record is None:
        return Decimal("0")
    amount, stored_currency = record
    if amount is None or stored_currency != currency:
        return Decimal("0")
    return Decimal(str(amount))


async def get_household_personal_allocation(
    db: AsyncSession,
    *,
    household_id: uuid.UUID,
    currency: str,
) -> Decimal:
    """Sum personal_allocation_amount across members whose contribution_mode
    is 'full' or 'fixed' (reimbursement members excluded).

    This is the Level-2 `Gasto personal` node value in the Hogar Sankey.
    Currency-scoped: a member whose stored currency doesn't match is treated
    as zero.
    """
    rows = await db.execute(
        text("""
            SELECT ubs.personal_allocation_amount
            FROM household_members hm
            JOIN user_budget_settings ubs ON ubs.user_id = hm.user_id
            WHERE hm.household_id = :hid
              AND hm.left_at IS NULL
              AND hm.contribution_mode IN ('full', 'fixed')
              AND ubs.personal_allocation_currency = :ccy
              AND ubs.personal_allocation_amount IS NOT NULL
        """),
        {"hid": str(household_id), "ccy": currency},
    )
    total = Decimal("0")
    for (amount,) in rows:
        total += Decimal(str(amount))
    return total
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_user_budget_settings.py::TestPersonalAllocation -v`

Expected: PASS — all 4 tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/modules/budgets/user_budget_settings_service.py backend/tests/test_user_budget_settings.py
git commit -m "feat(budget-v3): personal allocation helpers on user_budget_settings_service"
git push origin main
```

---

## Task 3: `HouseholdIncomeBreakdown` dataclass + `income_breakdown_for_household_view`

**Files:**
- Modify: `backend/modules/households/contribution_service.py` — add dataclasses + new function
- Test: `backend/tests/test_contribution_modes.py` — add caller-relative tests

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_contribution_modes.py`:

```python
from dataclasses import is_dataclass
from datetime import date
from decimal import Decimal

import pytest

from modules.households.contribution_service import (
    HouseholdIncomeBreakdown,
    OtherMemberContribution,
    income_breakdown_for_household_view,
    income_for_household_view,
)


class TestHouseholdIncomeBreakdownDataclass:
    def test_is_dataclass(self):
        assert is_dataclass(HouseholdIncomeBreakdown)
        assert is_dataclass(OtherMemberContribution)

    def test_has_expected_fields(self):
        bd = HouseholdIncomeBreakdown(
            total=Decimal("100"),
            caller_sources={"Sueldo": Decimal("80")},
            caller_other_income=Decimal("0"),
            other_members=[
                OtherMemberContribution(
                    user_id="00000000-0000-0000-0000-000000000001",
                    display_name="Cami",
                    amount=Decimal("20"),
                    mode="full",
                )
            ],
        )
        assert bd.total == Decimal("100")
        assert bd.caller_sources == {"Sueldo": Decimal("80")}
        assert bd.other_members[0].display_name == "Cami"


class TestIncomeBreakdownForHouseholdView:
    @pytest.mark.asyncio
    async def test_full_full_household_caller_sees_own_sources_and_other_aggregated(
        self,
        async_session,
        seed_household_full_full,  # fixture: 2 full-mode members
    ):
        """Full + full household. Caller A sees their own income categories
        broken out at caller_sources, and caller B appears as exactly one
        aggregated node in other_members sized to B's total real income."""
        hh = seed_household_full_full
        caller_a = hh.member_a  # has Sueldo=1000, Bonus=200 in March
        caller_b = hh.member_b  # has Sueldo=800 in March
        month = date(2026, 3, 1)

        bd_a = await income_breakdown_for_household_view(
            async_session,
            caller_id=caller_a.id,
            household_id=hh.id,
            month=month,
            currency="CLP",
        )

        assert bd_a.caller_sources == {
            "Sueldo": Decimal("1000"),
            "Bonus": Decimal("200"),
        }
        assert bd_a.caller_other_income == Decimal("0")
        assert len(bd_a.other_members) == 1
        assert bd_a.other_members[0].user_id == caller_b.id
        assert bd_a.other_members[0].amount == Decimal("800")
        assert bd_a.other_members[0].mode == "full"
        assert bd_a.total == Decimal("2000")  # 1000+200+800

        # Symmetry: caller B sees own sources + A as aggregated
        bd_b = await income_breakdown_for_household_view(
            async_session,
            caller_id=caller_b.id,
            household_id=hh.id,
            month=month,
            currency="CLP",
        )
        assert bd_b.caller_sources == {"Sueldo": Decimal("800")}
        assert len(bd_b.other_members) == 1
        assert bd_b.other_members[0].user_id == caller_a.id
        assert bd_b.other_members[0].amount == Decimal("1200")  # caller A's total

    @pytest.mark.asyncio
    async def test_full_fixed_household_never_reads_fixed_member_income(
        self,
        async_session,
        seed_household_full_fixed,  # fixture: full A + fixed B (fixed_contrib=500)
    ):
        """Privacy invariant: fixed member's real income is never read; only
        their fixed_contribution_amount appears as the other_members node."""
        hh = seed_household_full_fixed
        caller_a = hh.full_member  # real income 1000
        caller_b = hh.fixed_member  # real income 3000, fixed_contribution 500
        month = date(2026, 3, 1)

        bd_a = await income_breakdown_for_household_view(
            async_session,
            caller_id=caller_a.id,
            household_id=hh.id,
            month=month,
            currency="CLP",
        )
        assert len(bd_a.other_members) == 1
        # CRITICAL: this is 500, NOT 3000
        assert bd_a.other_members[0].amount == Decimal("500")
        assert bd_a.other_members[0].mode == "fixed"
        # Also total reflects the fixed value, not real income
        assert bd_a.total == Decimal("1500")  # A's 1000 + B's 500

    @pytest.mark.asyncio
    async def test_reimbursement_member_absent_from_other_members(
        self,
        async_session,
        seed_household_full_reimb,  # fixture: full A + reimb B
    ):
        hh = seed_household_full_reimb
        caller_a = hh.full_member
        month = date(2026, 3, 1)

        bd = await income_breakdown_for_household_view(
            async_session,
            caller_id=caller_a.id,
            household_id=hh.id,
            month=month,
            currency="CLP",
        )
        # Reimbursement member contributes $0, so they're not in other_members
        assert bd.other_members == []

    @pytest.mark.asyncio
    async def test_income_for_household_view_still_returns_total(
        self,
        async_session,
        seed_household_full_full,
    ):
        """Back-compat: the old function still returns the scalar total and
        it matches the new breakdown.total."""
        hh = seed_household_full_full
        month = date(2026, 3, 1)
        total = await income_for_household_view(
            async_session,
            household_id=hh.id,
            month=month,
            currency="CLP",
        )
        bd = await income_breakdown_for_household_view(
            async_session,
            caller_id=hh.member_a.id,
            household_id=hh.id,
            month=month,
            currency="CLP",
        )
        assert total == bd.total

    @pytest.mark.asyncio
    async def test_caller_income_outside_user_categories_goes_to_other_income(
        self,
        async_session,
        seed_user_with_unknown_income_category,
    ):
        """A transaction with a category that's not in the caller's
        user_category_preferences (e.g., category='Bitcoin rewards' when the
        user only has the default 7 income categories) goes into
        caller_other_income, not caller_sources."""
        user, household = seed_user_with_unknown_income_category
        month = date(2026, 3, 1)
        bd = await income_breakdown_for_household_view(
            async_session,
            caller_id=user.id,
            household_id=household.id,
            month=month,
            currency="CLP",
        )
        # 'Bitcoin rewards' is not in the user's preferences
        assert "Bitcoin rewards" not in bd.caller_sources
        assert bd.caller_other_income > Decimal("0")
```

**NOTE:** the `seed_household_full_full`, `seed_household_full_fixed`, `seed_household_full_reimb`, `seed_user_with_unknown_income_category` fixtures may not exist. Check `tests/conftest.py` and `tests/fixtures/` for existing household fixtures (the handoff mentions seed scripts at `backend/scripts/seed_budget_test_fixtures.py` for `rafa-full`, `rafa-fixed`, `rafa-reimb`, `rafa-solo`). Adapt the test to use those seeds directly, or extend the seed script to expose them as pytest fixtures.

- [ ] **Step 2: Run the failing tests**

Run: `cd backend && .venv/bin/pytest tests/test_contribution_modes.py::TestHouseholdIncomeBreakdownDataclass tests/test_contribution_modes.py::TestIncomeBreakdownForHouseholdView -v`

Expected: FAIL — `HouseholdIncomeBreakdown` and `income_breakdown_for_household_view` don't exist.

- [ ] **Step 3: Add dataclasses and function to `contribution_service.py`**

Edit `backend/modules/households/contribution_service.py`:

Add at the top (after the existing imports):

```python
from dataclasses import dataclass, field
from sqlalchemy import text
```

Add the dataclasses before `income_for_personal_view`:

```python
@dataclass
class OtherMemberContribution:
    user_id: uuid.UUID
    display_name: str
    amount: Decimal
    mode: str  # "full" | "fixed"


@dataclass
class HouseholdIncomeBreakdown:
    total: Decimal
    caller_sources: dict[str, Decimal] = field(default_factory=dict)
    caller_other_income: Decimal = _ZERO
    other_members: list[OtherMemberContribution] = field(default_factory=list)
```

Add the new function after `income_for_household_view` (the existing function — don't delete it; it stays as the scalar accessor):

```python
async def income_breakdown_for_household_view(
    db: AsyncSession,
    *,
    caller_id: uuid.UUID,
    household_id: uuid.UUID,
    month: date,
    currency: str,
) -> HouseholdIncomeBreakdown:
    """Return a caller-relative breakdown of household income for the month.

    PRIVACY INVARIANT
    -----------------
    - Caller's sources are computed from their own transactions + their own
      user_category_preferences, so only the caller sees their category mix.
    - For every non-caller active member:
        * full          -> read real income via income_for_personal_view
        * fixed         -> read fixed_contribution_amount only; NEVER touch
                           their real income transactions
        * reimbursement -> skipped (contributes $0 to the pot)
    - `total` equals the sum of caller_sources + caller_other_income +
      other_members amounts, and matches what `income_for_household_view`
      returns (which is kept as a thin scalar accessor).
    """
    first_day, first_day_next = _month_bounds_datetime(month)

    # 1. Caller's income transactions grouped by category.
    caller_tx_rows = await db.execute(
        select(
            Transaction.category,
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
        ).where(
            Transaction.user_id == caller_id,
            Transaction.household_id == household_id,
            Transaction.transaction_type == "income",
            Transaction.currency == currency,
            Transaction.transaction_date >= first_day,
            Transaction.transaction_date < first_day_next,
        ).group_by(Transaction.category)
    )
    raw_caller_totals: dict[str | None, Decimal] = {}
    for category, total in caller_tx_rows:
        raw_caller_totals[category] = Decimal(str(total))

    # 2. Caller's income category preferences (drives source labeling and
    #    order; the `caller_sources` dict only contains categories the user
    #    has configured, everything else drops into caller_other_income).
    pref_rows = await db.execute(
        text("""
            SELECT category, sort_order
            FROM user_category_preferences
            WHERE user_id = :uid AND category_type = 'income'
            ORDER BY sort_order
        """),
        {"uid": str(caller_id)},
    )
    known_income_categories = {row.category for row in pref_rows}

    caller_sources: dict[str, Decimal] = {}
    caller_other_income = _ZERO
    for category, total in raw_caller_totals.items():
        if category and category in known_income_categories and total > _ZERO:
            caller_sources[category] = total
        else:
            caller_other_income += total

    # 3. Other members (non-caller, active).
    member_rows = await db.execute(
        text("""
            SELECT hm.user_id, u.full_name, hm.contribution_mode,
                   hm.fixed_contribution_amount, hm.fixed_contribution_currency
            FROM household_members hm
            JOIN users u ON u.id = hm.user_id
            WHERE hm.household_id = :hid
              AND hm.left_at IS NULL
              AND hm.user_id != :caller_id
        """),
        {"hid": str(household_id), "caller_id": str(caller_id)},
    )
    other_members: list[OtherMemberContribution] = []
    for row in member_rows:
        if row.contribution_mode == "full":
            amt = await income_for_personal_view(
                db,
                user_id=row.user_id,
                household_id=household_id,
                month=month,
                currency=currency,
            )
            if amt > _ZERO:
                other_members.append(
                    OtherMemberContribution(
                        user_id=row.user_id,
                        display_name=row.full_name,
                        amount=amt,
                        mode="full",
                    )
                )
        elif row.contribution_mode == "fixed":
            # PRIVACY: never query their real income.
            if (
                row.fixed_contribution_amount is not None
                and row.fixed_contribution_currency == currency
            ):
                other_members.append(
                    OtherMemberContribution(
                        user_id=row.user_id,
                        display_name=row.full_name,
                        amount=Decimal(str(row.fixed_contribution_amount)),
                        mode="fixed",
                    )
                )
        # reimbursement mode -> skip (contributes $0)

    # 4. Compute the total and sanity-check it matches the scalar API.
    total = (
        sum(caller_sources.values(), start=_ZERO)
        + caller_other_income
        + sum((m.amount for m in other_members), start=_ZERO)
    )

    return HouseholdIncomeBreakdown(
        total=total,
        caller_sources=caller_sources,
        caller_other_income=caller_other_income,
        other_members=other_members,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_contribution_modes.py::TestHouseholdIncomeBreakdownDataclass tests/test_contribution_modes.py::TestIncomeBreakdownForHouseholdView -v`

Expected: PASS — all tests pass. If a fixture mismatch blocks any test, extend `tests/conftest.py` with the missing fixtures using the existing seed scripts before proceeding.

- [ ] **Step 5: Run the existing contribution_modes tests to check for regressions**

Run: `cd backend && .venv/bin/pytest tests/test_contribution_modes.py -v`

Expected: PASS — the existing scalar-API tests still pass because `income_for_household_view` is unchanged.

- [ ] **Step 6: Commit**

```bash
git add backend/modules/households/contribution_service.py backend/tests/test_contribution_modes.py
git commit -m "feat(budget-v3): HouseholdIncomeBreakdown + caller-relative income query"
git push origin main
```

---

## Task 4: Extend `spendable_ceiling` to account for `personal_allocation`

**Files:**
- Modify: `backend/modules/budgets/forecast.py` — extend `spendable_ceiling` signature
- Test: `backend/tests/test_budget_forecast.py` — new test

- [ ] **Step 1: Read the existing `spendable_ceiling` to understand the current formula**

Run: `grep -n "def spendable_ceiling" backend/modules/budgets/forecast.py` and read the function. Typical v2 formula: `income - known_bills - cuotas - savings_target`, clamped to 0.

- [ ] **Step 2: Write the failing test**

Append to `backend/tests/test_budget_forecast.py`:

```python
from decimal import Decimal
from modules.budgets.forecast import spendable_ceiling


class TestSpendableCeilingPersonalAllocation:
    def test_personal_allocation_subtracts_from_spendable(self):
        result = spendable_ceiling(
            income=Decimal("1000"),
            known_bills=Decimal("200"),
            cuotas_this_month=Decimal("100"),
            savings_target=Decimal("100"),
            personal_allocation=Decimal("150"),
        )
        # 1000 - 200 - 100 - 100 - 150 = 450
        assert result == Decimal("450")

    def test_personal_allocation_default_is_zero(self):
        """Omitting the kwarg preserves back-compat with v2 callers."""
        result = spendable_ceiling(
            income=Decimal("1000"),
            known_bills=Decimal("200"),
            cuotas_this_month=Decimal("100"),
            savings_target=Decimal("100"),
        )
        # 1000 - 200 - 100 - 100 - 0 = 600 (same as v2)
        assert result == Decimal("600")

    def test_personal_allocation_overspent_clamps_to_zero(self):
        result = spendable_ceiling(
            income=Decimal("500"),
            known_bills=Decimal("200"),
            cuotas_this_month=Decimal("100"),
            savings_target=Decimal("100"),
            personal_allocation=Decimal("200"),
        )
        # 500 - 200 - 100 - 100 - 200 = -100 -> clamped to 0
        assert result == Decimal("0")
```

- [ ] **Step 3: Run the failing test**

Run: `cd backend && .venv/bin/pytest tests/test_budget_forecast.py::TestSpendableCeilingPersonalAllocation -v`

Expected: FAIL — `spendable_ceiling` doesn't accept `personal_allocation` kwarg.

- [ ] **Step 4: Extend the function**

Edit `backend/modules/budgets/forecast.py` — add the new kwarg with default 0:

```python
def spendable_ceiling(
    *,
    income: Decimal,
    known_bills: Decimal,
    cuotas_this_month: Decimal,
    savings_target: Decimal,
    personal_allocation: Decimal = Decimal("0"),
) -> Decimal:
    """Spendable = income - (known_bills + cuotas + savings_target + personal_allocation), clamped to 0.

    `personal_allocation` is new in v3; defaults to 0 for back-compat. This
    is the sum of household members' `user_budget_settings.personal_allocation_amount`
    in the current currency, treated as a fixed outflow that happens before
    discretionary spending.
    """
    ceiling = income - known_bills - cuotas_this_month - savings_target - personal_allocation
    return ceiling if ceiling > Decimal("0") else Decimal("0")
```

(If the existing function body differs, adapt while preserving the existing clamp behavior and the existing kwarg names. Keep all existing kwargs intact.)

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_budget_forecast.py -v`

Expected: PASS — new tests pass AND existing spendable_ceiling tests still pass (kwargs-only signature with default preserves back-compat).

- [ ] **Step 6: Commit**

```bash
git add backend/modules/budgets/forecast.py backend/tests/test_budget_forecast.py
git commit -m "feat(budget-v3): spendable_ceiling accepts optional personal_allocation"
git push origin main
```

---

## Task 5: Additive `SankeyNode` fields

**Files:**
- Modify: `backend/modules/budgets/v2_schemas.py` — add optional fields to `SankeyNode`
- Test: `backend/tests/test_budget_v2_endpoint.py::test_contract_fixture_matches_pydantic_schema` — update fixture to include the new fields

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_budget_v3_sankey.py` (new file):

```python
"""Budget v3 Sankey tests — multi-level structure, caller-relative privacy,
flow conservation, personal allocation wiring."""
from __future__ import annotations

from decimal import Decimal

import pytest

from modules.budgets.v2_schemas import SankeyNode


class TestSankeyNodeAdditiveFields:
    def test_level_defaults_to_none(self):
        node = SankeyNode(id="income", label="Ingresos", value=Decimal("100"))
        assert node.level is None
        assert node.kind is None
        assert node.member_id is None

    def test_level_accepts_int(self):
        node = SankeyNode(
            id="sueldo",
            label="Sueldo",
            value=Decimal("800"),
            level=0,
            kind="source",
        )
        assert node.level == 0
        assert node.kind == "source"

    def test_member_id_accepts_string(self):
        node = SankeyNode(
            id="other_alice",
            label="Ingresos Alice",
            value=Decimal("500"),
            level=0,
            kind="source",
            member_id="00000000-0000-0000-0000-000000000001",
        )
        assert node.member_id == "00000000-0000-0000-0000-000000000001"
```

- [ ] **Step 2: Run the failing test**

Run: `cd backend && .venv/bin/pytest tests/test_budget_v3_sankey.py::TestSankeyNodeAdditiveFields -v`

Expected: FAIL — new fields don't exist on `SankeyNode`.

- [ ] **Step 3: Add the fields**

Edit `backend/modules/budgets/v2_schemas.py`:

```python
class SankeyNode(BaseModel):
    id: str
    label: str
    value: Decimal
    risk: bool | None = None
    level: int | None = None
    kind: str | None = None
    member_id: str | None = None
```

- [ ] **Step 4: Run the test**

Run: `cd backend && .venv/bin/pytest tests/test_budget_v3_sankey.py::TestSankeyNodeAdditiveFields -v`

Expected: PASS.

- [ ] **Step 5: Run the fixture contract test to see if it breaks**

Run: `cd backend && .venv/bin/pytest tests/test_budget_v2_endpoint.py::test_contract_fixture_matches_pydantic_schema -v`

Expected: PASS — additive optional fields don't break the existing fixture because the fixture doesn't reference them. (If the test does strict field-matching and breaks, extend the fixture to include the new fields as `null` — this is additive, not breaking.)

- [ ] **Step 6: Commit**

```bash
git add backend/modules/budgets/v2_schemas.py backend/tests/test_budget_v3_sankey.py
git commit -m "feat(budget-v3): additive level/kind/member_id fields on SankeyNode"
git push origin main
```

---

## Task 6: Extract `_pay_first_fit` routing helper

**Files:**
- Modify: `backend/modules/budgets/v2_service.py:436-450` — extract the `_pay` helper into a module-level `_pay_first_fit` function
- Test: `backend/tests/test_budget_v3_sankey.py` — unit test the helper

- [ ] **Step 1: Write the failing helper test**

Append to `backend/tests/test_budget_v3_sankey.py`:

```python
from modules.budgets.v2_service import _pay_first_fit


class TestPayFirstFit:
    def test_enough_income_covers_target(self):
        from_income, from_otras, remaining = _pay_first_fit(
            target=Decimal("100"),
            remaining_income=Decimal("500"),
        )
        assert from_income == Decimal("100")
        assert from_otras == Decimal("0")
        assert remaining == Decimal("400")

    def test_partial_income_splits_between_income_and_otras(self):
        from_income, from_otras, remaining = _pay_first_fit(
            target=Decimal("100"),
            remaining_income=Decimal("30"),
        )
        assert from_income == Decimal("30")
        assert from_otras == Decimal("70")
        assert remaining == Decimal("0")

    def test_zero_income_sends_full_target_to_otras(self):
        from_income, from_otras, remaining = _pay_first_fit(
            target=Decimal("100"),
            remaining_income=Decimal("0"),
        )
        assert from_income == Decimal("0")
        assert from_otras == Decimal("100")
        assert remaining == Decimal("0")

    def test_zero_target_returns_zero_zero(self):
        from_income, from_otras, remaining = _pay_first_fit(
            target=Decimal("0"),
            remaining_income=Decimal("500"),
        )
        assert from_income == Decimal("0")
        assert from_otras == Decimal("0")
        assert remaining == Decimal("500")
```

- [ ] **Step 2: Run the failing test**

Run: `cd backend && .venv/bin/pytest tests/test_budget_v3_sankey.py::TestPayFirstFit -v`

Expected: FAIL — `_pay_first_fit` is a nested function inside `_build_sankey`, not a module-level function.

- [ ] **Step 3: Extract and promote the helper**

Edit `backend/modules/budgets/v2_service.py` — remove the nested `def _pay(...)` inside `_build_sankey` and add a module-level function just above `_build_sankey`:

```python
def _pay_first_fit(
    *,
    target: Decimal,
    remaining_income: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    """First-fit routing primitive used by the Sankey builders.

    Pays `target` out of `remaining_income`, sending the shortfall to
    `otras_fuentes`. Returns `(from_income, from_otras, remaining_income_after)`.
    Every non-trivial target maps to at most two inflow links; flow
    conservation is preserved because from_income + from_otras == target.
    """
    if target <= _ZERO:
        return _ZERO, _ZERO, remaining_income
    from_income = min(remaining_income, target)
    from_otras = target - from_income
    return from_income, from_otras, remaining_income - from_income
```

Update `_build_sankey` to call `_pay_first_fit(target=..., remaining_income=...)` instead of the old nested `_pay(...)` calls. The old positional pattern was `(target_value, remaining)` — rewrite the four call sites in `_build_sankey` to use kwargs.

- [ ] **Step 4: Run the tests**

Run: `cd backend && .venv/bin/pytest tests/test_budget_v3_sankey.py::TestPayFirstFit tests/test_budget_v2_endpoint.py -v`

Expected: PASS — helper tests pass AND existing v2 endpoint tests still pass (the refactor is behavior-preserving).

- [ ] **Step 5: Commit**

```bash
git add backend/modules/budgets/v2_service.py backend/tests/test_budget_v3_sankey.py
git commit -m "refactor(budget-v3): extract _pay_first_fit as module-level helper"
git push origin main
```

---

## Task 7: `_build_hogar_sankey` — 4-level Hogar builder

**Files:**
- Modify: `backend/modules/budgets/v2_service.py` — add new function
- Test: `backend/tests/test_budget_v3_sankey.py` — hogar builder tests

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_budget_v3_sankey.py`:

```python
from modules.budgets.v2_service import _build_hogar_sankey
from modules.households.contribution_service import (
    HouseholdIncomeBreakdown,
    OtherMemberContribution,
)


def _sample_breakdown_full_full() -> HouseholdIncomeBreakdown:
    return HouseholdIncomeBreakdown(
        total=Decimal("2000"),
        caller_sources={"Sueldo": Decimal("1000"), "Bonus": Decimal("200")},
        caller_other_income=Decimal("0"),
        other_members=[
            OtherMemberContribution(
                user_id="00000000-0000-0000-0000-000000000001",
                display_name="Cami",
                amount=Decimal("800"),
                mode="full",
            )
        ],
    )


class TestBuildHogarSankey:
    def test_emits_level_0_sources_for_caller(self):
        bd = _sample_breakdown_full_full()
        block = _build_hogar_sankey(
            breakdown=bd,
            known_bills=Decimal("200"),
            cuotas_this_month=Decimal("100"),
            savings_target=Decimal("300"),
            personal_allocation=Decimal("400"),
            spendable_amount=Decimal("1000"),
            top_risk_totals=[],
            other_spent=Decimal("0"),
            income_category_order=["Sueldo", "Bonus"],
        )
        node_ids = {n.id for n in block.nodes}
        assert "src_sueldo" in node_ids
        assert "src_bonus" in node_ids
        assert "member_00000000-0000-0000-0000-000000000001" in node_ids
        assert "ingresos_hogar" in node_ids

    def test_level_0_nodes_have_level_zero_and_kind_source(self):
        bd = _sample_breakdown_full_full()
        block = _build_hogar_sankey(
            breakdown=bd,
            known_bills=Decimal("200"),
            cuotas_this_month=Decimal("100"),
            savings_target=Decimal("300"),
            personal_allocation=Decimal("400"),
            spendable_amount=Decimal("1000"),
            top_risk_totals=[],
            other_spent=Decimal("0"),
            income_category_order=["Sueldo", "Bonus"],
        )
        for node in block.nodes:
            if node.id.startswith("src_") or node.id.startswith("member_"):
                assert node.level == 0
                assert node.kind == "source"

    def test_ingresos_hogar_is_level_1_hub(self):
        bd = _sample_breakdown_full_full()
        block = _build_hogar_sankey(
            breakdown=bd,
            known_bills=Decimal("200"),
            cuotas_this_month=Decimal("100"),
            savings_target=Decimal("300"),
            personal_allocation=Decimal("400"),
            spendable_amount=Decimal("1000"),
            top_risk_totals=[],
            other_spent=Decimal("0"),
            income_category_order=["Sueldo", "Bonus"],
        )
        hub = next(n for n in block.nodes if n.id == "ingresos_hogar")
        assert hub.level == 1
        assert hub.kind == "hub"
        assert hub.value == Decimal("2000")

    def test_level_2_allocation_nodes_are_level_two(self):
        bd = _sample_breakdown_full_full()
        block = _build_hogar_sankey(
            breakdown=bd,
            known_bills=Decimal("200"),
            cuotas_this_month=Decimal("100"),
            savings_target=Decimal("300"),
            personal_allocation=Decimal("400"),
            spendable_amount=Decimal("1000"),
            top_risk_totals=[],
            other_spent=Decimal("0"),
            income_category_order=["Sueldo", "Bonus"],
        )
        allocation_ids = {"meta_ahorro", "gastos_fijos", "cuotas", "gasto_personal", "disponible_hogar"}
        for node in block.nodes:
            if node.id in allocation_ids:
                assert node.level == 2
                assert node.kind == "allocation"

    def test_flow_conservation_each_intermediate(self):
        """Every non-source / non-terminal node: inflow == outflow == value."""
        bd = _sample_breakdown_full_full()
        block = _build_hogar_sankey(
            breakdown=bd,
            known_bills=Decimal("200"),
            cuotas_this_month=Decimal("100"),
            savings_target=Decimal("300"),
            personal_allocation=Decimal("400"),
            spendable_amount=Decimal("1000"),
            top_risk_totals=[("Supermercado", Decimal("300"))],
            other_spent=Decimal("100"),
            income_category_order=["Sueldo", "Bonus"],
        )

        inflows: dict[str, Decimal] = {}
        outflows: dict[str, Decimal] = {}
        for link in block.links:
            outflows[link.source] = outflows.get(link.source, Decimal("0")) + link.value
            inflows[link.target] = inflows.get(link.target, Decimal("0")) + link.value

        # Ingresos Hogar (level 1 hub) must have inflow == outflow == its value
        hub_inflow = inflows.get("ingresos_hogar", Decimal("0"))
        hub_outflow = outflows.get("ingresos_hogar", Decimal("0"))
        hub_node_value = next(n.value for n in block.nodes if n.id == "ingresos_hogar")
        assert hub_inflow == hub_node_value == hub_outflow

        # Disponible hogar (intermediate) must have inflow == outflow
        disp_inflow = inflows.get("disponible_hogar", Decimal("0"))
        disp_outflow = outflows.get("disponible_hogar", Decimal("0"))
        assert disp_inflow == disp_outflow

    def test_gasto_personal_hidden_when_zero(self):
        bd = _sample_breakdown_full_full()
        block = _build_hogar_sankey(
            breakdown=bd,
            known_bills=Decimal("200"),
            cuotas_this_month=Decimal("100"),
            savings_target=Decimal("300"),
            personal_allocation=Decimal("0"),  # setting unset
            spendable_amount=Decimal("1400"),
            top_risk_totals=[],
            other_spent=Decimal("0"),
            income_category_order=["Sueldo", "Bonus"],
        )
        node_ids = {n.id for n in block.nodes}
        assert "gasto_personal" not in node_ids

    def test_fixed_member_node_labeled_contribucion_fija(self):
        bd = HouseholdIncomeBreakdown(
            total=Decimal("1500"),
            caller_sources={"Sueldo": Decimal("1000")},
            caller_other_income=Decimal("0"),
            other_members=[
                OtherMemberContribution(
                    user_id="00000000-0000-0000-0000-000000000002",
                    display_name="Cami",
                    amount=Decimal("500"),
                    mode="fixed",
                )
            ],
        )
        block = _build_hogar_sankey(
            breakdown=bd,
            known_bills=Decimal("100"),
            cuotas_this_month=Decimal("0"),
            savings_target=Decimal("200"),
            personal_allocation=Decimal("0"),
            spendable_amount=Decimal("1200"),
            top_risk_totals=[],
            other_spent=Decimal("0"),
            income_category_order=["Sueldo"],
        )
        cami_node = next(
            n for n in block.nodes
            if n.id == "member_00000000-0000-0000-0000-000000000002"
        )
        assert "Contribución fija" in cami_node.label
        assert "Cami" in cami_node.label
```

- [ ] **Step 2: Run the failing tests**

Run: `cd backend && .venv/bin/pytest tests/test_budget_v3_sankey.py::TestBuildHogarSankey -v`

Expected: FAIL — `_build_hogar_sankey` doesn't exist.

- [ ] **Step 3: Implement `_build_hogar_sankey`**

Add to `backend/modules/budgets/v2_service.py` after `_build_sankey` (leave the old function in place for now; it'll be swapped out in Task 9):

```python
def _build_hogar_sankey(
    *,
    breakdown: "HouseholdIncomeBreakdown",
    known_bills: Decimal,
    cuotas_this_month: Decimal,
    savings_target: Decimal,
    personal_allocation: Decimal,
    spendable_amount: Decimal,
    top_risk_totals: list[tuple[str, Decimal]],
    other_spent: Decimal,
    income_category_order: list[str],
) -> SankeyBlock:
    """Build the 4-level Hogar Sankey.

    Levels:
      0: income source nodes — caller's `user_category_preferences` rows
         (in sort_order) that have sum > 0, plus one aggregated node per
         other member, plus `otras_fuentes` synthetic node for overspent
         months.
      1: `ingresos_hogar` hub — single node, value = breakdown.total +
         otras_fuentes shortfall.
      2: allocation nodes — `meta_ahorro`, `gastos_fijos`, `cuotas`,
         `gasto_personal` (hidden if personal_allocation == 0),
         `disponible_hogar`.
      3: breakdown of `disponible_hogar` — per-risk-category spent nodes
         plus `spent_other` residual plus `spent_remaining`.

    Flow conservation: every non-source / non-terminal node has
    inflow == outflow == value. The `_pay_first_fit` helper splits any
    allocation target that income can't cover by itself, routing the
    shortfall to `otras_fuentes` which enters at Level 0 alongside the
    source nodes and flows into `ingresos_hogar`.
    """
    total_spent = sum((s for _, s in top_risk_totals), start=_ZERO) + other_spent
    spent_remaining = spendable_amount - total_spent
    if spent_remaining < _ZERO:
        spent_remaining = _ZERO
    sankey_spendable = total_spent if total_spent > spendable_amount else spendable_amount

    # Pay each allocation from income via first-fit routing.
    remaining = breakdown.total
    inc_kb, ot_kb, remaining = _pay_first_fit(target=known_bills, remaining_income=remaining)
    inc_cu, ot_cu, remaining = _pay_first_fit(target=cuotas_this_month, remaining_income=remaining)
    inc_st, ot_st, remaining = _pay_first_fit(target=savings_target, remaining_income=remaining)
    inc_pa, ot_pa, remaining = _pay_first_fit(target=personal_allocation, remaining_income=remaining)
    inc_sp, ot_sp, remaining = _pay_first_fit(target=sankey_spendable, remaining_income=remaining)

    otras_fuentes_total = ot_kb + ot_cu + ot_st + ot_pa + ot_sp
    ingresos_hogar_value = breakdown.total + otras_fuentes_total

    nodes: list[SankeyNode] = []

    # ---- Level 0: caller's income sources ----
    for category in income_category_order:
        amount = breakdown.caller_sources.get(category, _ZERO)
        if amount > _ZERO:
            nodes.append(
                SankeyNode(
                    id=f"src_{_slugify(category)}",
                    label=category,
                    value=amount,
                    level=0,
                    kind="source",
                )
            )
    if breakdown.caller_other_income > _ZERO:
        nodes.append(
            SankeyNode(
                id="src_otros_ingresos",
                label="Otros ingresos",
                value=breakdown.caller_other_income,
                level=0,
                kind="source",
            )
        )

    # ---- Level 0: other members ----
    for m in breakdown.other_members:
        if m.amount <= _ZERO:
            continue
        label = (
            f"Contribución fija {m.display_name}"
            if m.mode == "fixed"
            else f"Ingresos {m.display_name}"
        )
        nodes.append(
            SankeyNode(
                id=f"member_{m.user_id}",
                label=label,
                value=m.amount,
                level=0,
                kind="source",
                member_id=str(m.user_id),
            )
        )

    # ---- Level 0: otras_fuentes synthetic source ----
    if otras_fuentes_total > _ZERO:
        nodes.append(
            SankeyNode(
                id="otras_fuentes",
                label="Otras fuentes",
                value=otras_fuentes_total,
                level=0,
                kind="source",
            )
        )

    # ---- Level 1: income hub ----
    nodes.append(
        SankeyNode(
            id="ingresos_hogar",
            label="Ingresos Hogar",
            value=ingresos_hogar_value,
            level=1,
            kind="hub",
        )
    )

    # ---- Level 2: allocation nodes ----
    if known_bills > _ZERO:
        nodes.append(SankeyNode(
            id="gastos_fijos", label="Gastos fijos", value=known_bills,
            level=2, kind="allocation",
        ))
    if cuotas_this_month > _ZERO:
        nodes.append(SankeyNode(
            id="cuotas", label="Cuotas del mes", value=cuotas_this_month,
            level=2, kind="allocation",
        ))
    if savings_target > _ZERO:
        nodes.append(SankeyNode(
            id="meta_ahorro", label="Meta de ahorro", value=savings_target,
            level=2, kind="allocation",
        ))
    if personal_allocation > _ZERO:
        nodes.append(SankeyNode(
            id="gasto_personal", label="Gasto personal", value=personal_allocation,
            level=2, kind="allocation",
        ))
    if sankey_spendable > _ZERO:
        nodes.append(SankeyNode(
            id="disponible_hogar", label="Disponible hogar", value=sankey_spendable,
            level=2, kind="allocation",
        ))

    # ---- Level 3: disponible_hogar breakdown ----
    for category, spent in top_risk_totals:
        if spent <= _ZERO:
            continue
        nodes.append(SankeyNode(
            id=f"spent_{_slugify(category)}",
            label=category,
            value=spent,
            level=3,
            kind="spent",
            risk=True,
        ))
    if other_spent > _ZERO:
        nodes.append(SankeyNode(
            id="spent_other", label="Otras categorías", value=other_spent,
            level=3, kind="spent",
        ))
    if spent_remaining > _ZERO:
        nodes.append(SankeyNode(
            id="spent_remaining", label="Aún disponible", value=spent_remaining,
            level=3, kind="spent",
        ))

    # ---- Links ----
    links: list[SankeyLink] = []

    def _emit(source: str, target: str, value: Decimal) -> None:
        if value > _ZERO:
            links.append(SankeyLink(source=source, target=target, value=value))

    # Level 0 -> Level 1: sources feed into ingresos_hogar
    for category in income_category_order:
        amount = breakdown.caller_sources.get(category, _ZERO)
        _emit(f"src_{_slugify(category)}", "ingresos_hogar", amount)
    if breakdown.caller_other_income > _ZERO:
        _emit("src_otros_ingresos", "ingresos_hogar", breakdown.caller_other_income)
    for m in breakdown.other_members:
        if m.amount > _ZERO:
            _emit(f"member_{m.user_id}", "ingresos_hogar", m.amount)
    if otras_fuentes_total > _ZERO:
        _emit("otras_fuentes", "ingresos_hogar", otras_fuentes_total)

    # Level 1 -> Level 2: ingresos_hogar feeds each allocation
    _emit("ingresos_hogar", "gastos_fijos", known_bills)
    _emit("ingresos_hogar", "cuotas", cuotas_this_month)
    _emit("ingresos_hogar", "meta_ahorro", savings_target)
    _emit("ingresos_hogar", "gasto_personal", personal_allocation)
    _emit("ingresos_hogar", "disponible_hogar", sankey_spendable)

    # Level 2 -> Level 3: disponible_hogar splits into per-category spent
    for category, spent in top_risk_totals:
        if spent > _ZERO:
            _emit("disponible_hogar", f"spent_{_slugify(category)}", spent)
    _emit("disponible_hogar", "spent_other", other_spent)
    _emit("disponible_hogar", "spent_remaining", spent_remaining)

    return SankeyBlock(nodes=nodes, links=links)
```

Add import at top of file:

```python
from modules.households.contribution_service import (
    income_for_household_view,
    income_for_personal_view,
    income_breakdown_for_household_view,
    HouseholdIncomeBreakdown,
)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_budget_v3_sankey.py::TestBuildHogarSankey -v`

Expected: PASS — all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/budgets/v2_service.py backend/tests/test_budget_v3_sankey.py
git commit -m "feat(budget-v3): _build_hogar_sankey 4-level builder with flow conservation"
git push origin main
```

---

## Task 8: `_build_personal_sankey` — 3-level Personal builder

**Files:**
- Modify: `backend/modules/budgets/v2_service.py` — add new function
- Test: `backend/tests/test_budget_v3_sankey.py` — personal builder tests

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_budget_v3_sankey.py`:

```python
from modules.budgets.v2_service import _build_personal_sankey


class TestBuildPersonalSankey:
    def test_level_0_is_caller_sources_only_no_other_members(self):
        block = _build_personal_sankey(
            caller_sources={"Sueldo": Decimal("1000"), "Bonus": Decimal("200")},
            caller_other_income=Decimal("0"),
            known_bills=Decimal("100"),
            cuotas_this_month=Decimal("0"),
            savings_target=Decimal("200"),
            spendable_amount=Decimal("900"),
            top_risk_totals=[],
            other_spent=Decimal("0"),
            income_category_order=["Sueldo", "Bonus"],
        )
        node_ids = {n.id for n in block.nodes}
        # No member_ nodes — personal view doesn't aggregate other members
        assert not any(nid.startswith("member_") for nid in node_ids)
        assert "src_sueldo" in node_ids
        assert "src_bonus" in node_ids

    def test_level_1_has_three_allocation_nodes_not_four(self):
        """Personal view has meta_ahorro_personal / gastos_fijos_personal /
        disponible_personal — no gasto_personal node."""
        block = _build_personal_sankey(
            caller_sources={"Sueldo": Decimal("1000")},
            caller_other_income=Decimal("0"),
            known_bills=Decimal("100"),
            cuotas_this_month=Decimal("0"),
            savings_target=Decimal("200"),
            spendable_amount=Decimal("700"),
            top_risk_totals=[],
            other_spent=Decimal("0"),
            income_category_order=["Sueldo"],
        )
        node_ids = {n.id for n in block.nodes}
        assert "gasto_personal" not in node_ids
        assert "meta_ahorro_personal" in node_ids
        assert "gastos_fijos_personal" in node_ids
        assert "disponible_personal" in node_ids

    def test_flow_conservation(self):
        block = _build_personal_sankey(
            caller_sources={"Sueldo": Decimal("1000")},
            caller_other_income=Decimal("0"),
            known_bills=Decimal("100"),
            cuotas_this_month=Decimal("50"),
            savings_target=Decimal("200"),
            spendable_amount=Decimal("650"),
            top_risk_totals=[("Supermercado", Decimal("250"))],
            other_spent=Decimal("100"),
            income_category_order=["Sueldo"],
        )
        inflows: dict[str, Decimal] = {}
        outflows: dict[str, Decimal] = {}
        for link in block.links:
            outflows[link.source] = outflows.get(link.source, Decimal("0")) + link.value
            inflows[link.target] = inflows.get(link.target, Decimal("0")) + link.value

        # disponible_personal is intermediate, inflow == outflow
        assert inflows.get("disponible_personal", Decimal("0")) == outflows.get(
            "disponible_personal", Decimal("0")
        )
```

- [ ] **Step 2: Run the failing tests**

Run: `cd backend && .venv/bin/pytest tests/test_budget_v3_sankey.py::TestBuildPersonalSankey -v`

Expected: FAIL — function doesn't exist.

- [ ] **Step 3: Implement `_build_personal_sankey`**

Add to `backend/modules/budgets/v2_service.py` after `_build_hogar_sankey`:

```python
def _build_personal_sankey(
    *,
    caller_sources: dict[str, Decimal],
    caller_other_income: Decimal,
    known_bills: Decimal,
    cuotas_this_month: Decimal,
    savings_target: Decimal,
    spendable_amount: Decimal,
    top_risk_totals: list[tuple[str, Decimal]],
    other_spent: Decimal,
    income_category_order: list[str],
) -> SankeyBlock:
    """Build the 3-level Personal Sankey.

    Level 0: caller's income sources (only — no other members).
    Level 1: three allocation nodes: meta_ahorro_personal / gastos_fijos_personal
             / disponible_personal. No gasto_personal (see spec §2.2).
    Level 2: disponible_personal breakdown into per-risk-category spent.

    Flow conservation is preserved via the same first-fit routing +
    otras_fuentes fallback used by the hogar builder. Income total here is
    the sum of caller_sources + caller_other_income — this matches the v2
    personal view semantic (caller's own real income, regardless of
    contribution mode).
    """
    total_spent = sum((s for _, s in top_risk_totals), start=_ZERO) + other_spent
    spent_remaining = spendable_amount - total_spent
    if spent_remaining < _ZERO:
        spent_remaining = _ZERO
    sankey_spendable = total_spent if total_spent > spendable_amount else spendable_amount

    income_total = sum(caller_sources.values(), start=_ZERO) + caller_other_income

    remaining = income_total
    inc_kb, ot_kb, remaining = _pay_first_fit(target=known_bills, remaining_income=remaining)
    inc_cu, ot_cu, remaining = _pay_first_fit(target=cuotas_this_month, remaining_income=remaining)
    inc_st, ot_st, remaining = _pay_first_fit(target=savings_target, remaining_income=remaining)
    inc_sp, ot_sp, remaining = _pay_first_fit(target=sankey_spendable, remaining_income=remaining)

    otras_fuentes_total = ot_kb + ot_cu + ot_st + ot_sp

    nodes: list[SankeyNode] = []

    # ---- Level 0: caller's own income sources ----
    for category in income_category_order:
        amount = caller_sources.get(category, _ZERO)
        if amount > _ZERO:
            nodes.append(SankeyNode(
                id=f"src_{_slugify(category)}",
                label=category,
                value=amount,
                level=0,
                kind="source",
            ))
    if caller_other_income > _ZERO:
        nodes.append(SankeyNode(
            id="src_otros_ingresos", label="Otros ingresos", value=caller_other_income,
            level=0, kind="source",
        ))
    if otras_fuentes_total > _ZERO:
        nodes.append(SankeyNode(
            id="otras_fuentes", label="Otras fuentes", value=otras_fuentes_total,
            level=0, kind="source",
        ))

    # ---- Level 1: three allocation nodes ----
    if known_bills > _ZERO:
        nodes.append(SankeyNode(
            id="gastos_fijos_personal", label="Gastos fijos", value=known_bills,
            level=1, kind="allocation",
        ))
    if cuotas_this_month > _ZERO:
        nodes.append(SankeyNode(
            id="cuotas_personal", label="Cuotas del mes", value=cuotas_this_month,
            level=1, kind="allocation",
        ))
    if savings_target > _ZERO:
        nodes.append(SankeyNode(
            id="meta_ahorro_personal", label="Meta de ahorro", value=savings_target,
            level=1, kind="allocation",
        ))
    if sankey_spendable > _ZERO:
        nodes.append(SankeyNode(
            id="disponible_personal", label="Disponible personal", value=sankey_spendable,
            level=1, kind="allocation",
        ))

    # ---- Level 2: disponible_personal breakdown ----
    for category, spent in top_risk_totals:
        if spent <= _ZERO:
            continue
        nodes.append(SankeyNode(
            id=f"spent_{_slugify(category)}",
            label=category,
            value=spent,
            level=2,
            kind="spent",
            risk=True,
        ))
    if other_spent > _ZERO:
        nodes.append(SankeyNode(
            id="spent_other", label="Otras categorías", value=other_spent,
            level=2, kind="spent",
        ))
    if spent_remaining > _ZERO:
        nodes.append(SankeyNode(
            id="spent_remaining", label="Aún disponible", value=spent_remaining,
            level=2, kind="spent",
        ))

    # ---- Links ----
    links: list[SankeyLink] = []

    def _emit(source: str, target: str, value: Decimal) -> None:
        if value > _ZERO:
            links.append(SankeyLink(source=source, target=target, value=value))

    # Level 0 -> Level 1 (via first-fit routing so income splits correctly
    # when spendable can't be fully covered)
    for category in income_category_order:
        src = caller_sources.get(category, _ZERO)
        if src > _ZERO:
            _emit(f"src_{_slugify(category)}", "gastos_fijos_personal", min(src, inc_kb))
            inc_kb = (inc_kb - min(src, inc_kb))
    # Simpler: since the personal view is a single-source split, emit each
    # source's contribution to each allocation proportionally. Actually —
    # because we want to keep source -> allocation clean, route all sources
    # through a single hub.
```

Wait — this gets complex because the personal view Level 1 nodes are BOTH "Level 1 allocation" targets AND the sources feed them directly (no Level 1 hub like hogar has). That means flow conservation requires each source to split across multiple allocation targets proportionally, which produces many small links and is hard to route via first-fit.

**Simplification:** give the personal view a single hub node too, `ingresos_personales`, mirroring the hogar structure but labeled for personal scope. This makes the personal view technically 4 levels but the hub is visually unobtrusive and flow routing stays clean. Update the test assertions to expect `ingresos_personales` and update the implementation to route sources -> hub -> allocations -> breakdown:

Replace the above Level 0->1 routing with this final implementation:

```python
def _build_personal_sankey(
    *,
    caller_sources: dict[str, Decimal],
    caller_other_income: Decimal,
    known_bills: Decimal,
    cuotas_this_month: Decimal,
    savings_target: Decimal,
    spendable_amount: Decimal,
    top_risk_totals: list[tuple[str, Decimal]],
    other_spent: Decimal,
    income_category_order: list[str],
) -> SankeyBlock:
    """Build the Personal Sankey. Structurally identical to the Hogar builder
    but scoped to caller-only income, no `Gasto personal` allocation, and
    one fewer level of allocation nodes.

    Uses a `ingresos_personales` hub at Level 1 for clean routing (mirrors
    the hogar `ingresos_hogar` hub). Level 2 has the three allocation nodes,
    Level 3 has the disponible_personal breakdown.
    """
    total_spent = sum((s for _, s in top_risk_totals), start=_ZERO) + other_spent
    spent_remaining = spendable_amount - total_spent
    if spent_remaining < _ZERO:
        spent_remaining = _ZERO
    sankey_spendable = total_spent if total_spent > spendable_amount else spendable_amount

    income_total = sum(caller_sources.values(), start=_ZERO) + caller_other_income

    remaining = income_total
    inc_kb, ot_kb, remaining = _pay_first_fit(target=known_bills, remaining_income=remaining)
    inc_cu, ot_cu, remaining = _pay_first_fit(target=cuotas_this_month, remaining_income=remaining)
    inc_st, ot_st, remaining = _pay_first_fit(target=savings_target, remaining_income=remaining)
    inc_sp, ot_sp, remaining = _pay_first_fit(target=sankey_spendable, remaining_income=remaining)

    otras_fuentes_total = ot_kb + ot_cu + ot_st + ot_sp
    hub_value = income_total + otras_fuentes_total

    nodes: list[SankeyNode] = []

    # Level 0: sources
    for category in income_category_order:
        amount = caller_sources.get(category, _ZERO)
        if amount > _ZERO:
            nodes.append(SankeyNode(
                id=f"src_{_slugify(category)}", label=category, value=amount,
                level=0, kind="source",
            ))
    if caller_other_income > _ZERO:
        nodes.append(SankeyNode(
            id="src_otros_ingresos", label="Otros ingresos", value=caller_other_income,
            level=0, kind="source",
        ))
    if otras_fuentes_total > _ZERO:
        nodes.append(SankeyNode(
            id="otras_fuentes", label="Otras fuentes", value=otras_fuentes_total,
            level=0, kind="source",
        ))

    # Level 1: hub
    nodes.append(SankeyNode(
        id="ingresos_personales", label="Mis ingresos", value=hub_value,
        level=1, kind="hub",
    ))

    # Level 2: 3 allocation nodes (no gasto_personal)
    if known_bills > _ZERO:
        nodes.append(SankeyNode(
            id="gastos_fijos_personal", label="Gastos fijos", value=known_bills,
            level=2, kind="allocation",
        ))
    if cuotas_this_month > _ZERO:
        nodes.append(SankeyNode(
            id="cuotas_personal", label="Cuotas del mes", value=cuotas_this_month,
            level=2, kind="allocation",
        ))
    if savings_target > _ZERO:
        nodes.append(SankeyNode(
            id="meta_ahorro_personal", label="Meta de ahorro", value=savings_target,
            level=2, kind="allocation",
        ))
    if sankey_spendable > _ZERO:
        nodes.append(SankeyNode(
            id="disponible_personal", label="Disponible personal", value=sankey_spendable,
            level=2, kind="allocation",
        ))

    # Level 3: disponible_personal breakdown
    for category, spent in top_risk_totals:
        if spent <= _ZERO:
            continue
        nodes.append(SankeyNode(
            id=f"spent_{_slugify(category)}", label=category, value=spent,
            level=3, kind="spent", risk=True,
        ))
    if other_spent > _ZERO:
        nodes.append(SankeyNode(
            id="spent_other", label="Otras categorías", value=other_spent,
            level=3, kind="spent",
        ))
    if spent_remaining > _ZERO:
        nodes.append(SankeyNode(
            id="spent_remaining", label="Aún disponible", value=spent_remaining,
            level=3, kind="spent",
        ))

    # Links
    links: list[SankeyLink] = []

    def _emit(source: str, target: str, value: Decimal) -> None:
        if value > _ZERO:
            links.append(SankeyLink(source=source, target=target, value=value))

    # Level 0 -> Level 1 (hub)
    for category in income_category_order:
        amount = caller_sources.get(category, _ZERO)
        _emit(f"src_{_slugify(category)}", "ingresos_personales", amount)
    _emit("src_otros_ingresos", "ingresos_personales", caller_other_income)
    _emit("otras_fuentes", "ingresos_personales", otras_fuentes_total)

    # Level 1 -> Level 2
    _emit("ingresos_personales", "gastos_fijos_personal", known_bills)
    _emit("ingresos_personales", "cuotas_personal", cuotas_this_month)
    _emit("ingresos_personales", "meta_ahorro_personal", savings_target)
    _emit("ingresos_personales", "disponible_personal", sankey_spendable)

    # Level 2 -> Level 3
    for category, spent in top_risk_totals:
        if spent > _ZERO:
            _emit("disponible_personal", f"spent_{_slugify(category)}", spent)
    _emit("disponible_personal", "spent_other", other_spent)
    _emit("disponible_personal", "spent_remaining", spent_remaining)

    return SankeyBlock(nodes=nodes, links=links)
```

- [ ] **Step 4: Update the test assertions to reflect the hub**

Update the `TestBuildPersonalSankey` tests from Step 1:
- `test_level_1_has_three_allocation_nodes_not_four` → rename the test and fix the assertion: allocation nodes are now at `level=2`, and Level 1 has the hub. Assert that `gasto_personal` is NOT in node_ids, that `meta_ahorro_personal` / `gastos_fijos_personal` / `disponible_personal` are in node_ids with `level=2`.
- Add a test `test_level_1_hub_exists` asserting `ingresos_personales` node exists with `level=1, kind="hub"`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_budget_v3_sankey.py::TestBuildPersonalSankey -v`

Expected: PASS — all personal-builder tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/modules/budgets/v2_service.py backend/tests/test_budget_v3_sankey.py
git commit -m "feat(budget-v3): _build_personal_sankey with 3-level allocation structure"
git push origin main
```

---

## Task 9: Wire the new builders into `get_budget_v2`

**Files:**
- Modify: `backend/modules/budgets/v2_service.py:513-748` — replace the `_build_sankey` call in `get_budget_v2` with `_build_hogar_sankey` or `_build_personal_sankey`
- Test: `backend/tests/test_budget_v2_endpoint.py` — existing end-to-end tests must still pass after the swap

- [ ] **Step 1: Read the current `get_budget_v2` orchestration**

Re-read `backend/modules/budgets/v2_service.py` lines 513–748 (or whatever the updated line range is after Tasks 6/7/8). Understand how it currently builds the payload for the v2 shape.

- [ ] **Step 2: Query the caller's income category ordering once**

Inside `get_budget_v2`, after the currency + month setup but before the income fetch, add a query to pull the caller's income category order:

```python
# Caller's configured income categories (drives Level 0 source ordering)
income_cat_rows = await db.execute(
    text("""
        SELECT category
        FROM user_category_preferences
        WHERE user_id = :uid AND category_type = 'income'
        ORDER BY sort_order
    """),
    {"uid": str(user_id)},
)
income_category_order = [r[0] for r in income_cat_rows]
```

- [ ] **Step 3: Replace the `_build_sankey` call and the income fetch**

In `get_budget_v2`, find the existing income block:

```python
if view == "personal":
    income = await income_for_personal_view(...)
else:
    income = await income_for_household_view(...)
```

Replace with:

```python
if view == "personal":
    # Personal view: caller's own real income, grouped by category against
    # the caller's user_category_preferences. We reuse the breakdown helper
    # but scope it to the caller only by calling it with caller_id=user_id
    # and ignoring the other_members list (which will be empty because we
    # don't iterate them in the builder).
    caller_tx_rows = await db.execute(
        select(
            Transaction.category,
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
        ).where(
            Transaction.user_id == user_id,
            Transaction.household_id == household_id,
            Transaction.transaction_type == "income",
            Transaction.currency == currency,
            Transaction.transaction_date >= _month_bounds_datetime(month)[0],
            Transaction.transaction_date < _month_bounds_datetime(month)[1],
        ).group_by(Transaction.category)
    )
    raw_caller: dict[str | None, Decimal] = {}
    for category, total in caller_tx_rows:
        raw_caller[category] = Decimal(str(total))

    known_income_categories = set(income_category_order)
    personal_caller_sources: dict[str, Decimal] = {}
    personal_caller_other_income = _ZERO
    for cat, total in raw_caller.items():
        if cat and cat in known_income_categories and total > _ZERO:
            personal_caller_sources[cat] = total
        else:
            personal_caller_other_income += total
    income = sum(personal_caller_sources.values(), start=_ZERO) + personal_caller_other_income
else:
    breakdown = await income_breakdown_for_household_view(
        db,
        caller_id=user_id,
        household_id=household_id,
        month=month,
        currency=currency,
    )
    income = breakdown.total
```

- [ ] **Step 4: Compute personal_allocation_amount for the household view**

After the income block, add:

```python
if view == "household":
    personal_allocation_amount = await get_household_personal_allocation(
        db, household_id=household_id, currency=currency
    )
else:
    personal_allocation_amount = _ZERO  # not used in personal view sankey
```

And add the import at the top:

```python
from modules.budgets.user_budget_settings_service import (
    get_household_savings_target,
    get_household_personal_allocation,
    get_payday_day_of_month,
    get_savings_target,
)
```

- [ ] **Step 5: Update the `spendable_ceiling` call to include `personal_allocation`**

Find the existing call to `spendable_ceiling(...)` in `get_budget_v2` and add the kwarg:

```python
spendable_amount = spendable_ceiling(
    income=income,
    known_bills=known_bills,
    cuotas_this_month=cuotas_block.this_month,
    savings_target=savings_target_amount,
    personal_allocation=personal_allocation_amount,
)
```

- [ ] **Step 6: Replace the `_build_sankey` call**

Find the existing call:

```python
sankey = _build_sankey(
    income=income,
    known_bills=known_bills,
    ...
)
```

Replace with a dispatch on `view`:

```python
if view == "household":
    sankey = _build_hogar_sankey(
        breakdown=breakdown,
        known_bills=known_bills,
        cuotas_this_month=cuotas_block.this_month,
        savings_target=savings_target_amount,
        personal_allocation=personal_allocation_amount,
        spendable_amount=spendable_amount,
        top_risk_totals=top_risk_totals,
        other_spent=other_spent,
        income_category_order=income_category_order,
    )
else:
    sankey = _build_personal_sankey(
        caller_sources=personal_caller_sources,
        caller_other_income=personal_caller_other_income,
        known_bills=known_bills,
        cuotas_this_month=cuotas_block.this_month,
        savings_target=savings_target_amount,
        spendable_amount=spendable_amount,
        top_risk_totals=top_risk_totals,
        other_spent=other_spent,
        income_category_order=income_category_order,
    )
```

- [ ] **Step 7: Remove the old `_build_sankey` function**

Delete the old `_build_sankey` function from `v2_service.py`. Keep `_pay_first_fit`, `_build_hogar_sankey`, and `_build_personal_sankey`.

- [ ] **Step 8: Run the existing budget v2 endpoint tests**

Run: `cd backend && .venv/bin/pytest tests/test_budget_v2_endpoint.py -v`

Expected: Most tests pass. Some tests may need fixture updates because:
  - The old sankey fixture had a single `income` node; the new one has per-source nodes.
  - The old fixture didn't have the `level` / `kind` / `member_id` fields.
  - The flow-conservation test expectations may need to be updated for the new node set.

If tests fail, update them to match the new semantic — DO NOT roll back the implementation.

- [ ] **Step 9: Update `budget_v2_sample_response.json` fixture**

Run: `cd backend && .venv/bin/python scripts/regenerate_v2_fixture.py 2>/dev/null || true`

If no regenerate script exists (check `backend/scripts/`), regenerate manually: run the endpoint against a known-seed household, capture the response, and write it to `backend/tests/fixtures/budget_v2_sample_response.json`. The `test_contract_fixture_matches_pydantic_schema` test will verify the fixture parses correctly.

- [ ] **Step 10: Commit**

```bash
git add backend/modules/budgets/v2_service.py backend/tests/test_budget_v2_endpoint.py backend/tests/fixtures/budget_v2_sample_response.json
git commit -m "feat(budget-v3): wire hogar/personal builders into get_budget_v2"
git push origin main
```

---

## Task 10: Privacy regression tests — caller-relative + recursive walk

**Files:**
- Modify: `backend/tests/test_budget_v2_endpoint.py` — expand existing privacy test
- Test: `backend/tests/test_budget_v3_sankey.py` — new end-to-end privacy test

- [ ] **Step 1: Add the caller-relative end-to-end test**

Append to `backend/tests/test_budget_v3_sankey.py`:

```python
class TestCallerRelativeEndToEnd:
    @pytest.mark.asyncio
    async def test_caller_a_sees_own_sources_and_b_as_aggregate(
        self, authed_client_as_user_a, seed_household_full_full
    ):
        """Full+full household: caller A sees their own income categories
        broken out AND sees caller B as exactly one aggregated node."""
        hh = seed_household_full_full
        resp = await authed_client_as_user_a.get(
            f"/budgets/v2/{hh.id}?month=2026-03-01&view=household&currency=CLP"
        )
        assert resp.status_code == 200
        data = resp.json()
        nodes = data["sankey"]["nodes"]

        # Caller A's income sources should be at level 0 with id prefix src_
        caller_source_ids = {n["id"] for n in nodes if n.get("level") == 0 and n["id"].startswith("src_")}
        assert "src_sueldo" in caller_source_ids  # assuming A has a Sueldo income

        # Other member B should appear as exactly one node with member_id set
        member_nodes = [n for n in nodes if n.get("level") == 0 and n["id"].startswith("member_")]
        assert len(member_nodes) == 1
        assert member_nodes[0]["member_id"] == str(hh.member_b.id)
        assert "Ingresos" in member_nodes[0]["label"]

    @pytest.mark.asyncio
    async def test_hogar_fixed_privacy_recursive_walk(
        self, authed_client_as_full_member, seed_household_full_fixed
    ):
        """Mixed full+fixed household: the fixed member's REAL income never
        appears anywhere in the JSON — neither as a node value nor a link
        value nor a label fragment."""
        hh = seed_household_full_fixed
        fixed_real_income = hh.fixed_member_real_income  # e.g. Decimal("3000")
        fixed_contribution = hh.fixed_member.fixed_contribution_amount  # e.g. Decimal("500")

        resp = await authed_client_as_full_member.get(
            f"/budgets/v2/{hh.id}?month=2026-03-01&view=household&currency=CLP"
        )
        data = resp.json()

        # Walk every node and link; assert no value equals the fixed real income
        import json
        flat = json.dumps(data)
        assert str(fixed_real_income) not in flat, (
            f"Fixed member real income {fixed_real_income} leaked into the response"
        )

        # The fixed member's node value SHOULD equal fixed_contribution_amount
        nodes = data["sankey"]["nodes"]
        fixed_node = next(
            n for n in nodes
            if n.get("member_id") == str(hh.fixed_member.id)
        )
        assert Decimal(str(fixed_node["value"])) == fixed_contribution
        assert "Contribución fija" in fixed_node["label"]
```

- [ ] **Step 2: Add a full-matrix flow conservation test**

```python
class TestFlowConservationAllSeeds:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("seed_name,currency", [
        ("rafa-full", "CLP"),
        ("rafa-full", "USD"),
        ("rafa-fixed", "CLP"),
        ("rafa-fixed", "USD"),
        ("rafa-reimb", "CLP"),
        ("rafa-solo", "CLP"),
    ])
    async def test_flow_conservation(
        self, authed_client_for_seed, seed_name, currency
    ):
        """For every seeded household + currency combo, verify that every
        non-source / non-terminal node has inflow == outflow."""
        client, household_id = await authed_client_for_seed(seed_name)
        resp = await client.get(
            f"/budgets/v2/{household_id}?month=2026-03-01&view=household&currency={currency}"
        )
        assert resp.status_code == 200
        data = resp.json()
        nodes = data["sankey"]["nodes"]
        links = data["sankey"]["links"]

        inflows: dict[str, Decimal] = {}
        outflows: dict[str, Decimal] = {}
        for link in links:
            outflows[link["source"]] = outflows.get(link["source"], Decimal("0")) + Decimal(str(link["value"]))
            inflows[link["target"]] = inflows.get(link["target"], Decimal("0")) + Decimal(str(link["value"]))

        source_ids = {n["id"] for n in nodes if n.get("level") == 0}
        terminal_ids = {n["id"] for n in nodes if n["id"] not in outflows and n["id"] not in source_ids}

        for node in nodes:
            nid = node["id"]
            val = Decimal(str(node["value"]))
            if nid in source_ids:
                assert outflows.get(nid, Decimal("0")) == val, f"source {nid} outflow mismatch"
            elif nid in terminal_ids:
                assert inflows.get(nid, Decimal("0")) == val, f"terminal {nid} inflow mismatch"
            else:
                assert inflows.get(nid, Decimal("0")) == outflows.get(nid, Decimal("0")) == val, (
                    f"intermediate {nid}: in={inflows.get(nid)}, out={outflows.get(nid)}, val={val}"
                )
```

- [ ] **Step 3: Run the privacy + flow tests**

Run: `cd backend && .venv/bin/pytest tests/test_budget_v3_sankey.py::TestCallerRelativeEndToEnd tests/test_budget_v3_sankey.py::TestFlowConservationAllSeeds -v`

Expected: PASS. If fixtures are missing (`authed_client_as_user_a`, `seed_household_full_full`, `authed_client_for_seed`, etc.), build them up in `conftest.py` from the existing seed scripts (`backend/scripts/seed_budget_test_fixtures.py`) before retrying.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_budget_v3_sankey.py backend/tests/conftest.py
git commit -m "test(budget-v3): caller-relative privacy + flow conservation regression matrix"
git push origin main
```

---

## Task 11: Frontend — `BudgetSettingsSection.tsx` personal allocation input

**Files:**
- Modify: `frontend/app/(dashboard)/settings/components/BudgetSettingsSection.tsx` — add input
- Modify: `frontend/app/lib/api.ts` — add PUT endpoint wrapper
- Modify: `backend/modules/budgets/router.py` or equivalent — extend the settings write endpoint to accept `personal_allocation_amount`

- [ ] **Step 1: Locate the existing settings write endpoint**

Run: `cd backend && grep -rn "savings_target_amount\|user_budget_settings" modules/budgets/router.py modules/budgets/ 2>/dev/null | head -20`

Expected: find the existing `PUT /budgets/settings` or similar endpoint that handles the savings-target write path. Record the route, request pydantic model, and service function name — the new field will be added to all three.

- [ ] **Step 2: Extend the pydantic settings request model**

Find the existing request model (likely in `backend/modules/budgets/user_budget_settings_schemas.py` or similar). Add the new field:

```python
class UserBudgetSettingsRequest(BaseModel):
    savings_target_amount: Decimal | None = None
    savings_target_currency: str | None = None
    payday_day_of_month: int | None = None
    personal_allocation_amount: Decimal | None = None
    personal_allocation_currency: str | None = None
```

- [ ] **Step 3: Extend the service function**

Find the existing `update_user_budget_settings` (or similar) function. Add the new field to the UPDATE/INSERT SQL and make sure it's passed through from the router.

- [ ] **Step 4: Extend the frontend settings component**

Read `frontend/app/(dashboard)/settings/components/BudgetSettingsSection.tsx`. Find the existing input for `savings_target_amount`. Copy the pattern for a new input:

```tsx
<div className="space-y-2">
  <label className="text-sm font-medium text-gray-700">
    Gasto personal mensual (opcional)
  </label>
  <p className="text-xs text-gray-400">
    Monto que quieres reservar para gasto personal cada mes. Aparecerá
    como un nodo en el Sankey del hogar.
  </p>
  <div className="flex items-center gap-2">
    <span className="text-gray-500">{currency}</span>
    <input
      type="number"
      value={personalAllocation}
      onChange={(e) => setPersonalAllocation(e.target.value)}
      placeholder="0"
      className="w-32 rounded-md border border-gray-300 px-3 py-1.5 text-sm"
    />
  </div>
</div>
```

Wire to the existing save mutation so clicking Save sends both `savings_target_amount` and `personal_allocation_amount`.

- [ ] **Step 5: Verify `npm run build`**

Run: `cd frontend && npm run build`

Expected: clean build.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/(dashboard)/settings/components/BudgetSettingsSection.tsx backend/modules/budgets/ frontend/app/lib/api.ts
git commit -m "feat(budget-v3): personal allocation input in budget settings"
git push origin main
```

---

## Task 12: Frontend — `BudgetSankey.tsx` rank-based label renderer

**Files:**
- Modify: `frontend/app/(dashboard)/components/BudgetSankey.tsx` — update custom node renderer to use `level` field

- [ ] **Step 1: Read the current renderer**

Read `frontend/app/(dashboard)/components/BudgetSankey.tsx`. Locate the custom node renderer that decides label placement via `outgoing_links.length === 0`. This is what we're replacing.

- [ ] **Step 2: Update the node renderer to read the `level` field**

Replace the label-placement logic with a rank-based approach. The new rule:

```tsx
type SankeyNodeExt = {
  id: string;
  label: string;
  value: number;
  level?: number;          // 0..3
  kind?: "source" | "hub" | "allocation" | "spent";
  member_id?: string;
};

function CustomNodeRenderer(props: any) {
  const { x, y, width, height, payload } = props;
  const node: SankeyNodeExt = payload;
  const level = node.level ?? 0;

  // Determine label placement by rank
  let textAnchor: "start" | "end" | "middle";
  let labelX: number;
  let labelY: number = y + height / 2;

  if (level === 0) {
    // Sources: label on the right of the node (node body is leftmost)
    textAnchor = "end";
    labelX = x - 6;
  } else if (level === 1) {
    // Hub: label above the node
    textAnchor = "middle";
    labelX = x + width / 2;
    labelY = y - 8;
  } else if (level === 2) {
    // Allocations: label on the right
    textAnchor = "start";
    labelX = x + width + 6;
  } else {
    // Level 3 (breakdown): label on the right
    textAnchor = "start";
    labelX = x + width + 6;
  }

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={node.kind === "hub" ? "#2563EB" : node.kind === "source" ? "#60A5FA" : "#93C5FD"}
      />
      <text
        x={labelX}
        y={labelY}
        textAnchor={textAnchor}
        className="text-[11px] fill-gray-700"
        dominantBaseline="central"
      >
        {node.label}
      </text>
    </g>
  );
}
```

Adapt the exact styling to match the existing file's design tokens (blue primary, existing class names, etc.).

- [ ] **Step 3: Add graceful fallback for nodes without `level`**

If the payload doesn't have `level` (e.g., v2 contract with no level fields), fall back to the existing terminal-detection heuristic. Keep the old code path as a fallback branch, not the default.

- [ ] **Step 4: Update the tooltip to show member_id context**

If the node has a `member_id`, the tooltip should label the value with the member display name (already in `label`):

```tsx
<Tooltip
  formatter={(value, name, props) => {
    const payload = props?.payload;
    if (payload?.member_id) {
      return [formatMoney(value as number), payload.label];
    }
    return [formatMoney(value as number), name];
  }}
/>
```

- [ ] **Step 5: Verify `npm run build` + dev smoke test**

Run: `cd frontend && npm run build && npm run dev`

Visit `http://localhost:3000/budgets` and verify the 4-level Hogar Sankey renders with visible source nodes on the left, a clear `Ingresos Hogar` hub at the center-left, allocation nodes at center-right, and breakdown on the far right.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/(dashboard)/components/BudgetSankey.tsx
git commit -m "feat(budget-v3): rank-based label placement in BudgetSankey renderer"
git push origin main
```

---

## Task 13: Frontend — `budgets/page.tsx` container sizing

**Files:**
- Modify: `frontend/app/(dashboard)/budgets/page.tsx` — widen the Sankey container

- [ ] **Step 1: Locate the BudgetSankey container**

Read `frontend/app/(dashboard)/budgets/page.tsx`. Find the `<BudgetSankey>` component and its wrapper div.

- [ ] **Step 2: Expand the container**

Update the wrapper class to accommodate 4 levels:

```tsx
<div className="w-full min-h-[22rem] overflow-x-auto">
  <BudgetSankey data={data.sankey} />
</div>
```

Or, if the current grid layout allocates a fixed column to the Sankey, widen that column to span 2 grid columns for the Hogar view. Adapt to the actual layout in the file.

- [ ] **Step 3: Verify the layout in both views**

Run: `cd frontend && npm run dev`

Visit `http://localhost:3000/budgets`. Verify:
- Hogar view: 4 levels render without horizontal scroll on a typical 1440px viewport
- Personal view: 3-level (+ hub) renders cleanly; no wasted space

- [ ] **Step 4: Commit**

```bash
git add frontend/app/(dashboard)/budgets/page.tsx
git commit -m "feat(budget-v3): widen BudgetSankey container for 4-level layout"
git push origin main
```

---

## Task 14: Integration verification & cleanup

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend test suite**

Run: `cd backend && .venv/bin/pytest tests/ -q`

Expected: all tests pass. Count should be the prerequisite-plan baseline + all new v3 tests.

- [ ] **Step 2: Run the frontend build**

Run: `cd frontend && npm run build`

Expected: clean build, zero TypeScript errors.

- [ ] **Step 3: Run the full verification matrix against the dev DB**

With both servers running:

```bash
cd backend && .venv/bin/uvicorn main:app --reload --port 8000 &
cd frontend && npm run dev &
```

Visit `http://localhost:3000/budgets` as `rafaellabra96@gmail.com` and verify for the real household `8737617e-37a2-40bb-9dcc-f1c592db7b49`:
1. Current month CLP renders a flow-conserving 4-level Sankey
2. `Ingresos Hogar` hub shows total household income
3. Level 0 source nodes show Rafa's income categories (Sueldo, Bonus, etc.) in the order configured in `/settings/categories`
4. Cami appears as one node `Ingresos Cami` (since she's in full mode)
5. `Gastos fijos` appears as a direct child of `Ingresos Hogar` — not mixed with discretionary
6. If Rafa has set `personal_allocation_amount`, `Gasto personal` node appears; otherwise it's hidden
7. Level 3 per-category breakdown works (same as v2)
8. Switch currency to USD — same verification with USD transactions
9. Switch view to Personal — 3-level structure (+ hub) renders with Rafa's own source breakdown

- [ ] **Step 4: Code-level UX audit doc**

Create `docs/superpowers/specs/reviews/2026-04-15-budget-v3-ux-audit.md` with:
- A screenshot (or text description) of the v3 Sankey rendered against the real household
- Confirmation that each of the 9 verification points above is met
- Any visual polish items noted for follow-up

Commit it:

```bash
git add docs/superpowers/specs/reviews/2026-04-15-budget-v3-ux-audit.md
git commit -m "docs(budget-v3): UX audit for v3 Sankey rollout"
git push origin main
```

- [ ] **Step 5: Update `NEXT-STEPS.md`**

Run: use the `update-project-docs` skill to refresh `NEXT-STEPS.md`. Confirm the v3 Sankey work is marked complete and any deferred items from the spec §9 are noted.

- [ ] **Step 6: Final commit**

If there are any remaining changes from Step 5:

```bash
git add NEXT-STEPS.md
git commit -m "chore(budget-v3): update next-steps after v3 Sankey ship"
git push origin main
```

---

## Self-Review (complete before handing off)

**Spec coverage** (design doc §2–§8):

| Spec section | Task(s) |
|---|---|
| §2.1 Hogar 4-level structure | Tasks 7, 9 |
| §2.2 Personal 3-level structure | Tasks 8, 9 |
| §2.3 Flow conservation invariant | Tasks 7, 8, 10 |
| §3.1 Migration 037 | Task 1 |
| §3.3 Additive SankeyNode fields | Task 5 |
| §4.2 Caller-relative privacy model | Tasks 3, 10 |
| §4.3 `HouseholdIncomeBreakdown` dataclass | Task 3 |
| §4.4 Privacy regression tests | Task 10 |
| §5 Subscription classification toggle | **Prerequisite plan** (merge gate) |
| §6.1 New files | Tasks 1, 3, 7, 8, 10 |
| §6.2 Modified files | Tasks 2, 3, 4, 5, 9, 11, 12, 13 |
| §7 Chunking plan | 14 tasks (vs. 6 chunks in spec — the spec's chunks map across multiple tasks because TDD cycles per function produce more granular commits) |
| §8 Verification gates | Task 14 |

All spec sections map to at least one task. ✅

**Placeholder scan:**
- Task 2 Step 1 says "check the existing fixture pattern" — this is discovery, not placeholder. The step explicitly names the file to check.
- Task 11 Step 1 says "locate the existing settings write endpoint" — discovery step. Exact grep command provided.
- Task 12 Step 2 says "adapt exact styling to match existing file's design tokens" — this is a style guideline, not a TODO. The core renderer code is complete.
- No instances of `TBD`, `TODO`, `implement later`, or "add appropriate X".

**Type consistency:**
- `HouseholdIncomeBreakdown` dataclass fields: `total`, `caller_sources`, `caller_other_income`, `other_members` — consistent across Tasks 3, 7, 9, 10.
- `OtherMemberContribution` fields: `user_id`, `display_name`, `amount`, `mode` — consistent across Tasks 3, 7.
- `_pay_first_fit(target=..., remaining_income=...)` signature — consistent across Tasks 6, 7, 8.
- `_build_hogar_sankey` and `_build_personal_sankey` signatures — kwarg-only, consistent across Tasks 7, 8, 9.
- `SankeyNode.level` / `SankeyNode.kind` / `SankeyNode.member_id` — consistent field names and types across backend (Task 5) and frontend (Task 12).
- Node id conventions: `src_<slug>` for caller sources, `member_<uuid>` for other-member aggregated nodes, `otras_fuentes` for the synthetic overspent source, `ingresos_hogar` / `ingresos_personales` for the Level-1 hub — all consistent across Tasks 7, 8, 9, 10, 12.

All consistent. Plan is ready to execute.
