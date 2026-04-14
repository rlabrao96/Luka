"""Chunk E — CRUD tests for cuota_service.

These exercise create_cuota / list_active_cuotas / cancel_cuota against the
live dev DB via the `db` savepoint fixture. The `get_active_cuotas_summary`
month-boundary test also lives here since the boundary math is what the CRUD
feeds into.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

# Register all models so Base.metadata resolves every FK.
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
import modules.transactions.models  # noqa: F401
from modules.auth.models import User
from modules.budgets.cuota_service import (
    cancel_cuota,
    create_cuota,
    get_active_cuotas_summary,
    list_active_cuotas,
)
from modules.households.models import HouseholdMember


async def _get_seed_user(db, email: str) -> User:
    res = await db.execute(select(User).where(User.email == email))
    u = res.scalar_one_or_none()
    assert u is not None, f"seed missing: {email}"
    return u


async def _get_first_household_id(db, user_id: uuid.UUID) -> uuid.UUID:
    res = await db.execute(
        select(HouseholdMember.household_id).where(
            HouseholdMember.user_id == user_id,
            HouseholdMember.left_at.is_(None),
        )
    )
    return res.scalars().first()


@pytest.mark.asyncio
async def test_create_cuota_persists_with_computed_fields(db):
    user = await _get_seed_user(db, "rafa-full@luka.test")
    household_id = await _get_first_household_id(db, user.id)
    cuota = await create_cuota(
        db,
        user_id=user.id,
        household_id=household_id,
        merchant_name="Test Notebook",
        total_amount=Decimal("600000"),
        currency="CLP",
        installments_total=6,
        first_cuota_date=date(2026, 4, 1),
        split_type="personal",
    )
    assert cuota.monthly_amount == Decimal("100000.00")
    assert cuota.last_cuota_date == date(2026, 9, 1)  # first + 5 months
    assert cuota.status == "active"
    assert cuota.installments_paid == 0


@pytest.mark.asyncio
async def test_list_active_cuotas_scopes_to_user(db):
    user = await _get_seed_user(db, "rafa-full@luka.test")
    cuotas = await list_active_cuotas(db, scope="personal", user_id=user.id)
    assert all(c.status == "active" and c.user_id == user.id for c in cuotas)


@pytest.mark.asyncio
async def test_cancel_cuota_sets_status_cancelled(db):
    user = await _get_seed_user(db, "rafa-full@luka.test")
    household_id = await _get_first_household_id(db, user.id)
    new = await create_cuota(
        db,
        user_id=user.id,
        household_id=household_id,
        merchant_name="To Cancel",
        total_amount=Decimal("300000"),
        currency="CLP",
        installments_total=3,
        first_cuota_date=date(2026, 4, 1),
        split_type="personal",
    )
    await cancel_cuota(db, cuota_id=new.id, user_id=user.id)
    await db.refresh(new)
    assert new.status == "cancelled"


@pytest.mark.asyncio
async def test_month_boundary_cuota_last_month_active_this_month(db):
    """A cuota starting last month and ending this month counts as active for both."""
    user = await _get_seed_user(db, "rafa-full@luka.test")
    household_id = await _get_first_household_id(db, user.id)
    await create_cuota(
        db,
        user_id=user.id,
        household_id=household_id,
        merchant_name="Boundary",
        total_amount=Decimal("200000"),
        currency="CLP",
        installments_total=2,
        first_cuota_date=date(2026, 3, 1),  # last month
        split_type="personal",
    )
    summary_march = await get_active_cuotas_summary(
        db,
        scope="personal",
        user_id=user.id,
        month=date(2026, 3, 1),
        currency="CLP",
    )
    summary_april = await get_active_cuotas_summary(
        db,
        scope="personal",
        user_id=user.id,
        month=date(2026, 4, 1),
        currency="CLP",
    )
    # Boundary contributes 100k/month in both March and April.
    assert summary_march["this_month"] >= Decimal("100000")
    assert summary_april["this_month"] >= Decimal("100000")
