"""Integration tests for the `/budgets/v2/{household_id}` endpoint.

These hit the live dev DB via the `db` fixture from conftest and exercise
`get_budget_v2` at the service layer. We skip the HTTP/FastAPI layer on
purpose — FastAPI auth plumbing adds setup pain without extra coverage for
what we need to verify (service correctness, privacy invariants, and the
Pydantic contract).
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select, text

# Register all models with Base.metadata so relationship FKs resolve.
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.budgets.user_budget_settings_models import UserBudgetSettings
from modules.budgets.v2_schemas import BudgetV2Response
from modules.budgets.v2_service import get_budget_v2
from modules.households.models import Household
from modules.transactions.models import Transaction


# ------------------------------------------------- Day-1 contract fixture lock


def test_contract_fixture_matches_pydantic_schema():
    """Prevents drift between the committed contract fixture and the live schema.

    Chunks B, G, H build against the fixture; if the schema changes without
    updating the fixture (or vice versa), frontend breaks mid-sprint.
    """
    fixture = Path(__file__).parent / "fixtures" / "budget_v2_sample_response.json"
    with open(fixture) as f:
        data = json.load(f)
    BudgetV2Response.model_validate(data)


# ----------------------------------------------------------------- helpers


def _walk_json(obj):
    """Yield every leaf value in a nested dict/list structure."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_json(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_json(v)
    else:
        yield obj


def _assert_value_absent(obj, forbidden: Decimal) -> None:
    """Recursively assert `forbidden` never appears as a numeric leaf value."""
    forbidden_num = float(forbidden)
    for leaf in _walk_json(obj):
        if isinstance(leaf, (int, float, Decimal)):
            assert (
                float(leaf) != forbidden_num
            ), f"privacy breach: forbidden value {forbidden} surfaced in response"


async def _user_by_email(db, email: str) -> User:
    res = await db.execute(select(User).where(User.email == email))
    u = res.scalar_one_or_none()
    assert u is not None, f"seed missing: {email}"
    return u


async def _household_by_name(db, name: str) -> Household:
    res = await db.execute(select(Household).where(Household.name == name))
    h = res.scalar_one_or_none()
    assert h is not None, f"seed missing household: {name}"
    return h


def _current_month() -> date:
    today = date.today()
    return date(today.year, today.month, 1)


# ----------------------------------------------------------- HOGAR FULL tests


@pytest.mark.asyncio
async def test_hogar_full_personal_view_smoke(db):
    """rafa-full in personal view returns a valid response and a live cuota block."""
    user = await _user_by_email(db, "rafa-full@luka.test")
    household = await _household_by_name(db, "HOGAR FULL")

    resp = await get_budget_v2(
        db,
        household_id=household.id,
        user_id=user.id,
        month=_current_month(),
        currency="CLP",
        view="personal",
    )

    # Pydantic shape is valid
    assert isinstance(resp, BudgetV2Response)
    assert resp.view == "personal"
    assert resp.currency == "CLP"
    # Seed only has CLP for rafa-full — USD must not appear
    assert resp.currencies_available == ["CLP"]
    # Cuota seeded: 12 × 50k CLP, first 2026-02-01, last 2027-01-01 → alive this month
    assert resp.cuotas.this_month == Decimal("50000")
    assert resp.cuotas.active_count >= 1
    # Spendable remaining is clamped to >= 0 (display-safe). When income=0 (no
    # income txns in seed) the ceiling is 0 and the clamp kicks in — we just
    # verify the invariant that remaining is never negative.
    assert resp.spendable.remaining >= Decimal("0")
    assert resp.spendable.amount >= Decimal("0")


@pytest.mark.asyncio
async def test_hogar_full_household_view_smoke(db):
    """household view on HOGAR FULL returns a valid response."""
    user = await _user_by_email(db, "rafa-full@luka.test")
    household = await _household_by_name(db, "HOGAR FULL")

    resp = await get_budget_v2(
        db,
        household_id=household.id,
        user_id=user.id,
        month=_current_month(),
        currency="CLP",
        view="household",
    )
    assert resp.view == "household"
    # Both members contribute via `full` mode — since seed has no income rows,
    # income will be 0 but the call should not raise and should build a valid shape.
    assert isinstance(resp, BudgetV2Response)


# ------------------------------------------------- HOGAR FIXED — mixed currency


@pytest.mark.asyncio
async def test_hogar_fixed_currencies_available(db):
    """rafa-fixed has both CLP and USD txns — both must surface in the picker."""
    user = await _user_by_email(db, "rafa-fixed@luka.test")
    household = await _household_by_name(db, "HOGAR FIXED")

    resp = await get_budget_v2(
        db,
        household_id=household.id,
        user_id=user.id,
        month=_current_month(),
        currency="CLP",
        view="personal",
    )
    assert set(resp.currencies_available) == {"CLP", "USD"}


@pytest.mark.asyncio
async def test_hogar_fixed_household_income_respects_fixed_contribution(db):
    """household view income = sum(full:real, fixed:fixed_amount, reimb:0).

    Seed reality: neither rafa-fixed (full) nor partner-fixed (fixed) has
    income transactions — so full-mode real income = 0, fixed-mode amount
    = $800,000. Household total must equal exactly $800,000 CLP.
    """
    user = await _user_by_email(db, "rafa-fixed@luka.test")
    household = await _household_by_name(db, "HOGAR FIXED")

    resp = await get_budget_v2(
        db,
        household_id=household.id,
        user_id=user.id,
        month=_current_month(),
        currency="CLP",
        view="household",
    )

    # Household income: 0 (rafa-fixed full, no income txns) + 800k (partner fixed amount)
    income_node = next(n for n in resp.sankey.nodes if n.id == "income")
    assert income_node.value == Decimal(
        "800000"
    ), f"household income should be 800k (0 real + 800k fixed), got {income_node.value}"


@pytest.mark.asyncio
async def test_hogar_fixed_privacy_partner_amount_synthetic(db):
    """Privacy invariant: even when we SEED partner real income, household view
    must never leak the raw number.

    Seed the DB (inside the wrapping SAVEPOINT) with a synthetic income txn
    for partner-fixed so this test has something "forbidden" to sniff for.
    The conftest `db` fixture rolls back after, so the insert never persists.
    """
    partner = await _user_by_email(db, "partner-fixed@luka.test")
    rafa = await _user_by_email(db, "rafa-fixed@luka.test")
    household = await _household_by_name(db, "HOGAR FIXED")

    # Need a bank_account_id for the partner — grab any personal account.
    ba_row = await db.execute(
        text("SELECT id FROM bank_accounts WHERE user_id = :uid AND household_id = :hid LIMIT 1"),
        {"uid": str(partner.id), "hid": str(household.id)},
    )
    bank_account_id = ba_row.scalar_one()

    synthetic_partner_income = Decimal("2137913")  # recognizable non-round value
    month_start = _current_month()
    txn_date = datetime(month_start.year, month_start.month, 5, tzinfo=timezone.utc)

    db.add(
        Transaction(
            id=uuid.uuid4(),
            user_id=partner.id,
            household_id=household.id,
            bank_account_id=bank_account_id,
            raw_merchant_name="Nomina Empleador Test",
            amount=synthetic_partner_income,
            currency="CLP",
            transaction_date=txn_date,
            category="Sueldo",
            source="manual",
            source_type="manual",
            status="settled",
            transaction_type="income",
        )
    )
    await db.flush()

    resp = await get_budget_v2(
        db,
        household_id=household.id,
        user_id=rafa.id,
        month=month_start,
        currency="CLP",
        view="household",
    )

    payload = resp.model_dump(mode="json")
    _assert_value_absent(payload, synthetic_partner_income)

    # And positively assert: household income should still be 0 real + 800k fixed
    # = 800k (partner is fixed mode, so their real income does NOT count).
    income_node = next(n for n in resp.sankey.nodes if n.id == "income")
    assert income_node.value == Decimal("800000")


# ----------------------------------------------- savings-category exclusion


@pytest.mark.asyncio
async def test_investment_category_excluded_from_spendable_spent(db):
    """Transactions in savings-equivalent categories (e.g. 'Inversión')
    must NOT count as `spendable.spent` — they're savings, not spending.
    They should count toward `savings_target.progress` instead.
    """
    user = await _user_by_email(db, "rafa-solo@luka.test")
    household = await _household_by_name(db, "HOGAR SOLO")

    # Ensure no user_budget_settings target row is set — we only care about
    # progress for this test. (Target may be 0, pct_complete should be 0.)
    await db.execute(
        text("DELETE FROM user_budget_settings WHERE user_id = :uid"),
        {"uid": str(user.id)},
    )
    await db.flush()

    resp = await get_budget_v2(
        db,
        household_id=household.id,
        user_id=user.id,
        month=_current_month(),
        currency="CLP",
        view="personal",
    )

    # Seed includes an "Inversión" category at 80,000 CLP per month.
    # Make sure that 80,000 shows up in savings progress and NOT in spendable.spent.
    assert resp.savings_target.progress >= Decimal("80000")
    # None of the spent nodes should carry the Inversión category
    spent_labels = [n.label.lower() for n in resp.sankey.nodes if n.id.startswith("spent_")]
    assert "inversion" not in spent_labels and "inversión" not in spent_labels


# ----------------------------------------------- savings target from settings


@pytest.mark.asyncio
async def test_savings_target_reads_from_user_budget_settings(db):
    """Set a user_budget_settings row and verify the service echoes it back."""
    user = await _user_by_email(db, "rafa-solo@luka.test")
    household = await _household_by_name(db, "HOGAR SOLO")

    # Upsert a target row (rolled back by the conftest fixture).
    await db.execute(
        text("DELETE FROM user_budget_settings WHERE user_id = :uid"),
        {"uid": str(user.id)},
    )
    db.add(
        UserBudgetSettings(
            user_id=user.id,
            savings_target_amount=Decimal("250000"),
            savings_target_currency="CLP",
            payday_day_of_month=25,
        )
    )
    await db.flush()

    resp = await get_budget_v2(
        db,
        household_id=household.id,
        user_id=user.id,
        month=_current_month(),
        currency="CLP",
        view="personal",
    )
    assert resp.savings_target.target == Decimal("250000")
    # pct_complete = progress / target; progress comes from Inversión seed ≈ 80,000
    assert resp.savings_target.pct_complete > Decimal("0")
