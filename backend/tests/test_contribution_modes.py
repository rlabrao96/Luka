"""Regression tests for the contribution_service module (Chunk D).

These exercise the extracted contribution-mode helpers directly — bypassing
`get_budget_v2` — so a future refactor (or an accidental widening of the
query) is caught at the narrowest possible surface.

The privacy invariant under test:
    For a household member with `contribution_mode='fixed'`, their REAL
    income transactions must never be read or returned by the household-
    view income calculator. Only `fixed_contribution_amount` counts.

These complement the end-to-end check in
`test_budget_v2_endpoint.py::test_hogar_fixed_privacy_partner_amount_synthetic`
by pinning the behavior at the service boundary. If `v2_service.py` changes
(e.g. inlines a query again), the endpoint test still catches it; if this
module is refactored, this file catches it first.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select, text

# Register all models so Base.metadata resolves FKs.
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.contribution_service import (
    HouseholdIncomeBreakdown,
    OtherMemberContribution,
    income_breakdown_for_household_view,
    income_for_household_view,
    income_for_personal_view,
)
from modules.households.models import Household
from modules.transactions.models import Transaction


# ----------------------------------------------------------------- helpers


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


async def _insert_income(
    db,
    *,
    user_id: uuid.UUID,
    household_id: uuid.UUID,
    amount: Decimal,
    currency: str = "CLP",
) -> None:
    """Insert a synthetic income transaction inside the wrapping SAVEPOINT."""
    ba_row = await db.execute(
        text("SELECT id FROM bank_accounts WHERE user_id = :uid AND household_id = :hid LIMIT 1"),
        {"uid": str(user_id), "hid": str(household_id)},
    )
    bank_account_id = ba_row.scalar_one()

    month_start = _current_month()
    txn_date = datetime(month_start.year, month_start.month, 5, tzinfo=timezone.utc)
    db.add(
        Transaction(
            id=uuid.uuid4(),
            user_id=user_id,
            household_id=household_id,
            bank_account_id=bank_account_id,
            raw_merchant_name="Nomina Test",
            amount=amount,
            currency=currency,
            transaction_date=txn_date,
            category="Sueldo",
            source="manual",
            source_type="manual",
            status="settled",
            transaction_type="income",
        )
    )
    await db.flush()


# ----------------------------------------------------------- household view


@pytest.mark.asyncio
async def test_household_view_sums_full_real_plus_fixed_amount(db):
    """HOGAR FIXED with synthetic income seeded for both members.

    rafa-fixed is in `full` mode → contributes real income (1,234,567).
    partner-fixed is in `fixed` mode → contributes 800,000 (NOT their
    2,137,913 of real income).

    Expected total: 1,234,567 + 800,000 = 2,034,567.
    """
    rafa = await _user_by_email(db, "rafa-fixed@luka.test")
    partner = await _user_by_email(db, "partner-fixed@luka.test")
    household = await _household_by_name(db, "HOGAR FIXED")

    rafa_real_income = Decimal("1234567")
    partner_real_income = Decimal("2137913")  # forbidden leak value

    await _insert_income(db, user_id=rafa.id, household_id=household.id, amount=rafa_real_income)
    await _insert_income(
        db, user_id=partner.id, household_id=household.id, amount=partner_real_income
    )

    total = await income_for_household_view(
        db,
        household_id=household.id,
        month=_current_month(),
        currency="CLP",
    )

    expected = rafa_real_income + Decimal("800000")  # 2,034,567
    assert total == expected, (
        f"household income should be {expected} "
        f"(rafa full {rafa_real_income} + partner fixed 800k), got {total}"
    )
    # Privacy: partner's real income must never equal the returned total.
    assert total != partner_real_income, (
        "PRIVACY BREACH: household total matched partner's REAL income — "
        "fixed-mode member's income leaked into the household view"
    )
    # Sanity: the forbidden value must not appear anywhere in the total path
    # (would only match if logic pulled raw income for fixed members).
    assert total - Decimal("800000") != partner_real_income


@pytest.mark.asyncio
async def test_household_view_reimbursement_mode_contributes_zero(db):
    """HOGAR REIMB: rafa is `full`, partner is `reimbursement`.

    Even though partner-reimb has seeded real income, reimbursement members
    contribute nothing to the household pot. The household total should
    equal ONLY rafa's real income, and must never surface partner's.
    """
    rafa = await _user_by_email(db, "rafa-reimb@luka.test")
    partner = await _user_by_email(db, "partner-reimb@luka.test")
    household = await _household_by_name(db, "HOGAR REIMB")

    rafa_real = Decimal("900000")
    partner_real = Decimal("700000")  # must NOT appear in the total

    await _insert_income(db, user_id=rafa.id, household_id=household.id, amount=rafa_real)
    await _insert_income(db, user_id=partner.id, household_id=household.id, amount=partner_real)

    total = await income_for_household_view(
        db,
        household_id=household.id,
        month=_current_month(),
        currency="CLP",
    )
    assert total == rafa_real, (
        f"household income should equal ONLY rafa's {rafa_real} "
        f"(partner is reimbursement -> 0), got {total}"
    )
    assert total != (
        rafa_real + partner_real
    ), "reimbursement member's income leaked into the household pot"


# -------------------------------------------------------------- personal view


@pytest.mark.asyncio
async def test_personal_view_fixed_member_sees_own_real_income(db):
    """partner-fixed in personal view sees their REAL income (not fixed amount).

    Personal view is the member's own scope — they're allowed to see their
    own real income. The fixed-amount redaction only applies to household view.
    """
    partner = await _user_by_email(db, "partner-fixed@luka.test")
    household = await _household_by_name(db, "HOGAR FIXED")

    real = Decimal("2137913")
    await _insert_income(db, user_id=partner.id, household_id=household.id, amount=real)

    personal = await income_for_personal_view(
        db,
        user_id=partner.id,
        household_id=household.id,
        month=_current_month(),
        currency="CLP",
    )
    assert (
        personal == real
    ), f"personal view should return partner's real income {real}, got {personal}"


@pytest.mark.asyncio
async def test_personal_view_full_member_sees_own_real_income(db):
    """rafa-fixed (full mode) in personal view returns their real income."""
    rafa = await _user_by_email(db, "rafa-fixed@luka.test")
    household = await _household_by_name(db, "HOGAR FIXED")

    real = Decimal("1234567")
    await _insert_income(db, user_id=rafa.id, household_id=household.id, amount=real)

    personal = await income_for_personal_view(
        db,
        user_id=rafa.id,
        household_id=household.id,
        month=_current_month(),
        currency="CLP",
    )
    assert (
        personal == real
    ), f"personal view should return rafa's real income {real}, got {personal}"


# ---------------------------------------------------------- shared helper sanity


def test_walk_json_helper_finds_forbidden_value():
    """Quick sanity check on the shared helper — the real regression is above."""
    from tests.helpers.json_walk import assert_value_absent

    payload = {"income": {"nodes": [{"value": "2137913.00"}]}}
    try:
        assert_value_absent(payload, Decimal("2137913"))
    except AssertionError:
        return
    raise AssertionError("helper failed to spot forbidden value")


# ------------------------------------------------------ breakdown helpers


async def _get_seed_user(db) -> User:
    res = await db.execute(select(User).where(User.email == "rafa-full@luka.test"))
    u = res.scalar_one_or_none()
    assert u is not None, "seed missing: rafa-full@luka.test"
    return u


async def _get_seed_household_id(db, user_id) -> uuid.UUID:
    res = await db.execute(
        text(
            "SELECT household_id FROM household_members "
            "WHERE user_id = :uid AND left_at IS NULL LIMIT 1"
        ),
        {"uid": str(user_id)},
    )
    hid = res.scalar_one_or_none()
    assert hid is not None, f"seed user {user_id} has no active household"
    return hid


# ---------------------------------------- dataclass structural tests


class TestHouseholdIncomeBreakdownDataclass:
    def test_is_dataclass(self):
        from dataclasses import is_dataclass

        assert is_dataclass(HouseholdIncomeBreakdown)
        assert is_dataclass(OtherMemberContribution)

    def test_has_expected_fields(self):
        bd = HouseholdIncomeBreakdown(
            total=Decimal("100"),
            caller_sources={"Sueldo": Decimal("80")},
            caller_other_income=Decimal("0"),
            other_members=[
                OtherMemberContribution(
                    user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                    display_name="Cami",
                    amount=Decimal("20"),
                    mode="full",
                )
            ],
        )
        assert bd.total == Decimal("100")
        assert bd.caller_sources == {"Sueldo": Decimal("80")}
        assert bd.other_members[0].display_name == "Cami"


# ---------------------------------------- integration tests


class TestIncomeBreakdownForHouseholdView:
    @pytest.mark.asyncio
    async def test_caller_relative_for_seed_user(self, db):
        """Smoke test against the rafa-full seeded household. The new
        breakdown function must return a HouseholdIncomeBreakdown whose
        total exactly matches what income_for_household_view returns."""
        user = await _get_seed_user(db)
        household_id = await _get_seed_household_id(db, user.id)
        month = date(2026, 3, 1)

        bd = await income_breakdown_for_household_view(
            db,
            caller_id=user.id,
            household_id=household_id,
            month=month,
            currency="CLP",
        )
        scalar_total = await income_for_household_view(
            db,
            household_id=household_id,
            month=month,
            currency="CLP",
        )
        assert bd.total == scalar_total

    @pytest.mark.asyncio
    async def test_caller_sources_keys_match_user_categories(self, db):
        """Caller's income transactions whose category appears in their
        user_category_preferences (category_type='income') go into
        caller_sources; everything else goes into caller_other_income."""
        user = await _get_seed_user(db)
        household_id = await _get_seed_household_id(db, user.id)
        month = date(2026, 3, 1)

        # Read the caller's configured income categories
        cat_rows = await db.execute(
            text("""
                SELECT category FROM user_category_preferences
                WHERE user_id = :uid AND category_type = 'income'
            """),
            {"uid": str(user.id)},
        )
        configured_income_cats = {r[0] for r in cat_rows}

        bd = await income_breakdown_for_household_view(
            db,
            caller_id=user.id,
            household_id=household_id,
            month=month,
            currency="CLP",
        )
        # Every key in caller_sources must be one of the user's configured
        # income categories — no orphaned categories should sneak in
        for key in bd.caller_sources:
            assert (
                key in configured_income_cats
            ), f"Source '{key}' not in configured income categories"

    @pytest.mark.asyncio
    async def test_other_members_excludes_caller_themselves(self, db):
        """The caller must never appear in their own other_members list."""
        user = await _get_seed_user(db)
        household_id = await _get_seed_household_id(db, user.id)
        month = date(2026, 3, 1)

        bd = await income_breakdown_for_household_view(
            db,
            caller_id=user.id,
            household_id=household_id,
            month=month,
            currency="CLP",
        )
        for m in bd.other_members:
            assert m.user_id != user.id, "Caller must not appear in other_members"

    @pytest.mark.asyncio
    async def test_total_equals_components_sum(self, db):
        """total == sum(caller_sources) + caller_other_income + sum(other_members.amount)"""
        user = await _get_seed_user(db)
        household_id = await _get_seed_household_id(db, user.id)
        month = date(2026, 3, 1)

        bd = await income_breakdown_for_household_view(
            db,
            caller_id=user.id,
            household_id=household_id,
            month=month,
            currency="CLP",
        )
        components = (
            sum(bd.caller_sources.values(), start=Decimal("0"))
            + bd.caller_other_income
            + sum((m.amount for m in bd.other_members), start=Decimal("0"))
        )
        assert bd.total == components
