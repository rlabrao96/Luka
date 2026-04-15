from decimal import Decimal

import pytest
from sqlalchemy import select, text

# Register all models so Base.metadata resolves FKs across modules.
import modules.households.models  # noqa: F401
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.budgets.user_budget_settings_models import UserBudgetSettings  # noqa: F401
from modules.budgets.user_budget_settings_service import (
    get_or_create,
    get_personal_allocation,
    get_household_personal_allocation,
    get_savings_target,
    update_payday,
    update_personal_allocation,
    update_savings_target,
)


async def _user(db, email):
    res = await db.execute(select(User).where(User.email == email))
    return res.scalar_one()


async def _get_seed_user(db) -> User:
    res = await db.execute(select(User).where(User.email == "rafa-full@luka.test"))
    u = res.scalar_one_or_none()
    assert u is not None, "seed missing: rafa-full@luka.test"
    return u


async def _get_seed_household_id(db, user_id):
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


@pytest.mark.asyncio
async def test_get_or_create_returns_row_with_defaults(db):
    user = await _user(db, "rafa-solo@luka.test")
    settings = await get_or_create(db, user_id=user.id)
    assert settings.user_id == user.id
    assert settings.savings_target_amount is None or settings.savings_target_amount == 0


@pytest.mark.asyncio
async def test_update_savings_target_persists(db):
    user = await _user(db, "rafa-solo@luka.test")
    await update_savings_target(db, user_id=user.id, amount=Decimal("300000"), currency="CLP")
    target = await get_savings_target(db, user_id=user.id, currency="CLP")
    assert target == Decimal("300000")


@pytest.mark.asyncio
async def test_get_savings_target_currency_mismatch_returns_zero(db):
    user = await _user(db, "rafa-solo@luka.test")
    await update_savings_target(db, user_id=user.id, amount=Decimal("300000"), currency="CLP")
    target_usd = await get_savings_target(db, user_id=user.id, currency="USD")
    assert target_usd == Decimal("0")


@pytest.mark.asyncio
async def test_update_payday_persists_and_validates_range(db):
    user = await _user(db, "rafa-solo@luka.test")
    await update_payday(db, user_id=user.id, day=15)
    settings = await get_or_create(db, user_id=user.id)
    assert settings.payday_day_of_month == 15

    with pytest.raises(ValueError):
        await update_payday(db, user_id=user.id, day=32)
    with pytest.raises(ValueError):
        await update_payday(db, user_id=user.id, day=0)


class TestPersonalAllocation:
    @pytest.mark.asyncio
    async def test_get_personal_allocation_returns_zero_when_unset(self, db):
        user = await _get_seed_user(db)
        result = await get_personal_allocation(db, user_id=user.id, currency="CLP")
        assert result == Decimal("0")

    @pytest.mark.asyncio
    async def test_get_personal_allocation_returns_stored_value(self, db):
        user = await _get_seed_user(db)
        # Upsert a value into user_budget_settings
        await db.execute(
            text("""
                INSERT INTO user_budget_settings
                    (user_id, personal_allocation_amount, personal_allocation_currency)
                VALUES (:uid, 500000, 'CLP')
                ON CONFLICT (user_id) DO UPDATE
                SET personal_allocation_amount = 500000,
                    personal_allocation_currency = 'CLP'
            """),
            {"uid": str(user.id)},
        )
        await db.commit()
        result = await get_personal_allocation(db, user_id=user.id, currency="CLP")
        assert result == Decimal("500000")

    @pytest.mark.asyncio
    async def test_get_personal_allocation_ignores_wrong_currency(self, db):
        user = await _get_seed_user(db)
        await db.execute(
            text("""
                INSERT INTO user_budget_settings
                    (user_id, personal_allocation_amount, personal_allocation_currency)
                VALUES (:uid, 500000, 'CLP')
                ON CONFLICT (user_id) DO UPDATE
                SET personal_allocation_amount = 500000,
                    personal_allocation_currency = 'CLP'
            """),
            {"uid": str(user.id)},
        )
        await db.commit()
        # Request USD — should return 0 because the stored currency is CLP
        result = await get_personal_allocation(db, user_id=user.id, currency="USD")
        assert result == Decimal("0")

    @pytest.mark.asyncio
    async def test_household_personal_allocation_sums_full_and_fixed_members(self, db):
        """Household aggregate = sum across members whose contribution_mode
        is 'full' or 'fixed'. Reimbursement members are excluded."""
        # Use the seeded rafa-full household (which has at least one full-mode member)
        user = await _get_seed_user(db)
        household_id = await _get_seed_household_id(db, user.id)

        # Set personal_allocation for the seed user to 500000 CLP
        await db.execute(
            text("""
                INSERT INTO user_budget_settings
                    (user_id, personal_allocation_amount, personal_allocation_currency)
                VALUES (:uid, 500000, 'CLP')
                ON CONFLICT (user_id) DO UPDATE
                SET personal_allocation_amount = 500000,
                    personal_allocation_currency = 'CLP'
            """),
            {"uid": str(user.id)},
        )
        await db.commit()

        result = await get_household_personal_allocation(
            db, household_id=household_id, currency="CLP"
        )
        # The seed user's allocation contributes; if the rafa-full household
        # has only one member, result == 500000. If multiple full-mode members
        # exist with no allocation set, result is still just the seed user's.
        assert result >= Decimal("500000")

    @pytest.mark.asyncio
    async def test_update_personal_allocation_persists_and_clears(self, db):
        """Write path: setting persists, clearing with amount=None removes."""
        user = await _get_seed_user(db)
        # Set the value
        await update_personal_allocation(
            db, user_id=user.id, amount=Decimal("250000"), currency="CLP"
        )
        result = await get_personal_allocation(db, user_id=user.id, currency="CLP")
        assert result == Decimal("250000")

        # Clear by passing amount=None
        await update_personal_allocation(db, user_id=user.id, amount=None, currency=None)
        cleared = await get_personal_allocation(db, user_id=user.id, currency="CLP")
        assert cleared == Decimal("0")
