"""Service for user_budget_settings (savings target + payday).

Chunk C wrote inline reads for savings target and payday; this module
centralizes them. Privacy: each row is keyed on user_id — household_id is
NOT stored here, so the household view aggregates by joining active
members from household_members.

Per spec Section 5.2: reimbursement members do not contribute to the
household pot, so their personal savings targets are excluded from the
household aggregate. full + fixed members are summed.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.budgets.user_budget_settings_models import UserBudgetSettings
from modules.households.models import HouseholdMember

_ZERO = Decimal("0")


async def get_or_create(db: AsyncSession, *, user_id: uuid.UUID) -> UserBudgetSettings:
    """Fetch the user's settings row, creating it with null defaults if missing."""
    res = await db.execute(select(UserBudgetSettings).where(UserBudgetSettings.user_id == user_id))
    row = res.scalar_one_or_none()
    if row is not None:
        return row
    row = UserBudgetSettings(user_id=user_id)
    db.add(row)
    await db.flush()
    return row


async def update_savings_target(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    amount: Decimal | None,
    currency: str | None,
) -> UserBudgetSettings:
    """Set the caller's monthly savings target and its currency.

    Passing `amount=None` clears the target. `currency` must match the
    caller's active budget currency at read time — mismatches are reported
    as 0 in `get_savings_target`.
    """
    row = await get_or_create(db, user_id=user_id)
    row.savings_target_amount = amount
    row.savings_target_currency = currency
    await db.flush()
    return row


async def update_personal_allocation(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    amount: Decimal | None,
    currency: str | None,
) -> UserBudgetSettings:
    """Set (or clear with ``amount=None``) the user's monthly personal spending allocation.

    This value is used as the Level-2 ``Gasto personal`` node in the Sankey
    when viewed in household mode. Passing ``amount=None`` removes the node
    from the household Sankey for this user.
    """
    row = await get_or_create(db, user_id=user_id)
    row.personal_allocation_amount = amount
    row.personal_allocation_currency = currency
    await db.flush()
    return row


async def update_payday(
    db: AsyncSession, *, user_id: uuid.UUID, day: int | None
) -> UserBudgetSettings:
    """Set (or clear with `day=None`) the caller's payday day-of-month.

    Raises ValueError on out-of-range values to mirror the DB CHECK
    constraint (1..31 inclusive).
    """
    if day is not None and not (1 <= day <= 31):
        raise ValueError("payday_day_of_month must be between 1 and 31")
    row = await get_or_create(db, user_id=user_id)
    row.payday_day_of_month = day
    await db.flush()
    return row


async def get_savings_target(db: AsyncSession, *, user_id: uuid.UUID, currency: str) -> Decimal:
    """Return the user's savings target in the requested currency, or 0 if mismatch."""
    row = await get_or_create(db, user_id=user_id)
    if row.savings_target_amount is None:
        return _ZERO
    # If the stored target is in a different currency, ignore it for this view.
    if row.savings_target_currency and row.savings_target_currency != currency:
        return _ZERO
    return Decimal(str(row.savings_target_amount))


async def get_household_savings_target(
    db: AsyncSession, *, household_id: uuid.UUID, currency: str
) -> Decimal:
    """Sum savings targets across active household members in the given currency.

    Per spec Section 5.2: reimbursement members don't contribute to the
    household pot, so their personal savings targets are excluded. full +
    fixed are summed.
    """
    stmt = select(HouseholdMember.user_id, HouseholdMember.contribution_mode).where(
        HouseholdMember.household_id == household_id,
        HouseholdMember.left_at.is_(None),
    )
    result = await db.execute(stmt)
    members = list(result)
    total = _ZERO
    for member_user_id, mode in members:
        if mode == "reimbursement":
            continue
        total += await get_savings_target(db, user_id=member_user_id, currency=currency)
    return total


async def get_payday_day_of_month(db: AsyncSession, *, user_id: uuid.UUID) -> int | None:
    """Return the user's payday day-of-month, or None if unset."""
    row = await get_or_create(db, user_id=user_id)
    return row.payday_day_of_month


async def get_personal_allocation(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    currency: str,
) -> Decimal:
    """Read the user's personal_allocation_amount in the requested currency.

    Returns Decimal('0') when no row exists or when the stored
    personal_allocation_currency does not match the requested currency.

    Unlike `get_savings_target`, this helper is read-only: it does NOT
    create a `user_budget_settings` row as a side effect. Callers that
    expect auto-creation should explicitly upsert via the settings router.
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
