from decimal import Decimal

import pytest
from sqlalchemy import select

from modules.auth.models import User
from modules.budgets.user_budget_settings_models import UserBudgetSettings  # noqa: F401
from modules.budgets.user_budget_settings_service import (
    get_or_create,
    get_savings_target,
    update_payday,
    update_savings_target,
)


async def _user(db, email):
    res = await db.execute(select(User).where(User.email == email))
    return res.scalar_one()


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
