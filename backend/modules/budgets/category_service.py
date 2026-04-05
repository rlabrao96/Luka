import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from modules.households.models import CategoryBudget


async def get_category_budgets(
    db: AsyncSession,
    household_id: uuid.UUID,
    month: date,
) -> dict:
    result = await db.execute(
        select(CategoryBudget).where(
            CategoryBudget.household_id == household_id,
            CategoryBudget.month == month,
        )
    )
    rows = result.scalars().all()
    return {
        "household_id": str(household_id),
        "month": month.isoformat(),
        "budgets": [{"category": r.category, "amount": float(r.amount)} for r in rows],
    }


async def set_category_budgets(
    db: AsyncSession,
    household_id: uuid.UUID,
    month: date,
    budgets: list[dict],
) -> dict:
    # Delete existing budgets for this month, then insert new ones
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
                amount=b["amount"],
            )
        )
    await db.commit()
    return await get_category_budgets(db, household_id, month)
