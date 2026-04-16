# backend/modules/currencies/service.py
import uuid
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from modules.auth.models import User
from modules.auth.schemas import ALLOWED_CURRENCIES
from modules.currencies.models import UserCurrency

_ALLOWED = ALLOWED_CURRENCIES  # shorthand


async def get_currencies(db: AsyncSession, user_id: uuid.UUID) -> list[UserCurrency]:
    """Return user's active currencies sorted by sort_order. Auto-seeds if empty."""
    result = await db.execute(
        select(UserCurrency)
        .where(UserCurrency.user_id == user_id)
        .order_by(UserCurrency.sort_order)
    )
    rows = result.scalars().all()

    if not rows:
        # Seed from preferred_currency
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        preferred = user.preferred_currency if user and user.preferred_currency else "CLP"

        db.add(UserCurrency(
            user_id=user_id,
            currency_code=preferred,
            is_primary=True,
            sort_order=0,
        ))
        await db.commit()

        result = await db.execute(
            select(UserCurrency)
            .where(UserCurrency.user_id == user_id)
            .order_by(UserCurrency.sort_order)
        )
        rows = result.scalars().all()

    return list(rows)


async def add_currency(
    db: AsyncSession, user_id: uuid.UUID, currency_code: str
) -> UserCurrency:
    """Add a currency to the user's active list. Returns new row."""
    if currency_code not in _ALLOWED:
        raise ValueError(f"Not supported: {currency_code}")

    # Duplicate check
    dup = await db.execute(
        select(UserCurrency).where(
            UserCurrency.user_id == user_id,
            UserCurrency.currency_code == currency_code,
        )
    )
    if dup.scalar_one_or_none() is not None:
        raise ValueError(f"Already in list: {currency_code}")

    # Next sort_order
    max_result = await db.execute(
        select(func.max(UserCurrency.sort_order)).where(UserCurrency.user_id == user_id)
    )
    max_order = max_result.scalar()
    next_order = (max_order + 1) if max_order is not None else 0

    row = UserCurrency(
        user_id=user_id,
        currency_code=currency_code,
        is_primary=False,
        sort_order=next_order,
    )
    db.add(row)
    await db.commit()
    return row


async def delete_currency(
    db: AsyncSession, user_id: uuid.UUID, currency_code: str
) -> None:
    """Remove a currency. Promotes next if it was primary. Raises if it's the last."""
    result = await db.execute(
        select(UserCurrency)
        .where(UserCurrency.user_id == user_id)
        .order_by(UserCurrency.sort_order)
    )
    rows = result.scalars().all()

    if len(rows) <= 1:
        raise ValueError("Debes tener al menos una moneda activa")

    target = next((r for r in rows if r.currency_code == currency_code), None)
    if target is None:
        return  # already gone

    if target.is_primary:
        # Promote the row with the lowest sort_order among the rest
        remaining = [r for r in rows if r.currency_code != currency_code]
        promoted = min(remaining, key=lambda r: r.sort_order)
        promoted.is_primary = True
        target.is_primary = False

        # Sync users.preferred_currency
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(preferred_currency=promoted.currency_code)
        )

    # Use ORM delete (not raw SQL) so the session identity map stays consistent
    await db.delete(target)
    await db.commit()


async def sync_preferred_currency(
    db: AsyncSession, user_id: uuid.UUID, new_currency: str
) -> None:
    """Sync user_currencies to match new preferred_currency.

    Does NOT commit — the caller (PATCH /auth/me) commits once after both
    the users table update and this sync, keeping both changes in one transaction.
    """
    result = await db.execute(
        select(UserCurrency)
        .where(UserCurrency.user_id == user_id)
        .order_by(UserCurrency.sort_order)
    )
    rows = result.scalars().all()

    if not rows:
        # Table empty — insert as primary
        db.add(UserCurrency(
            user_id=user_id,
            currency_code=new_currency,
            is_primary=True,
            sort_order=0,
        ))
        return

    existing = {r.currency_code: r for r in rows}

    if new_currency in existing:
        # Already in list — flip primaries
        for r in rows:
            r.is_primary = r.currency_code == new_currency
    else:
        # Not in list — insert and flip
        for r in rows:
            r.is_primary = False
        max_order = max(r.sort_order for r in rows)
        db.add(UserCurrency(
            user_id=user_id,
            currency_code=new_currency,
            is_primary=True,
            sort_order=max_order + 1,
        ))
