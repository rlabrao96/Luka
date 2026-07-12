"""Per-category monthly caps (category_budgets table).

LIVE code — backs /budgets/categories, consumed by the caps editor and the
dashboard category bars. amounts are integer MINOR units per currency
(migration 052); each row carries its own currency.
"""

import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from modules.households.models import CategoryBudget


async def get_category_budgets(
    db: AsyncSession,
    household_id: uuid.UUID,
    month: date,
    currency: str | None = None,
) -> dict:
    """Return category caps for a household/month, optionally filtered to a
    single currency. When `currency` is None, returns rows across every
    currency a household has set caps in."""
    stmt = select(CategoryBudget).where(
        CategoryBudget.household_id == household_id,
        CategoryBudget.month == month,
    )
    if currency:
        stmt = stmt.where(CategoryBudget.currency == currency)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return {
        "household_id": str(household_id),
        "month": month.isoformat(),
        "budgets": [
            {"category": r.category, "amount": float(r.amount), "currency": r.currency}
            for r in rows
        ],
    }


async def set_category_budgets(
    db: AsyncSession,
    household_id: uuid.UUID,
    month: date,
    budgets: list[dict],
) -> dict:
    """Replace all caps for `(household_id, month)` with the provided list.

    Each row carries its own `currency`, so a single save can mix, e.g.,
    Alimentación in CLP and Travel in USD. Categories in the table but
    absent from the payload are dropped (explicit deletion is the UI's
    "clear" action).
    """
    await db.execute(
        delete(CategoryBudget).where(
            CategoryBudget.household_id == household_id,
            CategoryBudget.month == month,
        )
    )
    for b in budgets:
        db.add(
            CategoryBudget(
                household_id=household_id,
                category=b["category"],
                month=month,
                currency=b.get("currency", "CLP"),
                amount=b["amount"],
            )
        )
    await db.commit()
    return await get_category_budgets(db, household_id, month)
