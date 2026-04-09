# backend/modules/budgets/allocation_service.py
import uuid
from datetime import date, datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from modules.households.models import HouseholdBudgetAllocation, BankAccount
from modules.transactions.models import Transaction, TransactionSplit

DEFAULT_ALLOCATION = {"hogar_pct": 50.0, "ahorro_pct": 20.0, "personal_pct": 30.0}
RECOMMENDED_LABEL = "Regla 50/20/30"


def _round5(value: float) -> float:
    """Round to nearest 5."""
    return round(value / 5) * 5


def compute_historical_suggestion(
    monthly_data: list[dict],
) -> dict | None:
    """
    Given a list of {income, hogar_spent, personal_spent} dicts,
    compute the average allocation rounded to nearest 5%.
    Returns None if no months have valid income data.
    """
    valid = [m for m in monthly_data if m.get("income", 0) > 0]
    if not valid:
        return None

    avg_hogar_pct = sum(m["hogar_spent"] / m["income"] * 100 for m in valid) / len(valid)
    avg_personal_pct = sum(m["personal_spent"] / m["income"] * 100 for m in valid) / len(valid)
    avg_ahorro_pct = 100 - avg_hogar_pct - avg_personal_pct

    hogar = _round5(avg_hogar_pct)
    ahorro = max(0.0, _round5(avg_ahorro_pct))
    personal = 100.0 - hogar - ahorro

    return {"hogar_pct": hogar, "ahorro_pct": ahorro, "personal_pct": personal}


async def get_allocation(
    db: AsyncSession,
    household_id: uuid.UUID,
    month: date,
    currency: str | None = None,
) -> dict:
    """Return current allocation + a historical 50/20/30 suggestion.

    When ``currency`` is provided, the historical averages are computed from
    transactions in that currency only. Without the filter, CLP and USD would
    be summed together and the suggested percentages would be meaningless.
    """
    result = await db.execute(
        select(HouseholdBudgetAllocation).where(
            HouseholdBudgetAllocation.household_id == household_id,
            HouseholdBudgetAllocation.month == month,
        )
    )
    alloc = result.scalar_one_or_none()

    allocation_block = (
        {
            "hogar_pct": float(alloc.hogar_pct),
            "ahorro_pct": float(alloc.ahorro_pct),
            "personal_pct": float(alloc.personal_pct),
            "is_default": False,
        }
        if alloc
        else {**DEFAULT_ALLOCATION, "is_default": True}
    )

    # Historical suggestion: look at last 3 months
    monthly_data = []
    for offset in range(1, 4):
        m = month.month - offset
        y = month.year
        while m <= 0:
            m += 12
            y -= 1

        # Get personal account IDs for the household
        personal_acc_result = await db.execute(
            select(BankAccount.id).where(
                BankAccount.household_id == household_id,
                BankAccount.account_type == "personal",
                BankAccount.is_active.is_(True),
            )
        )
        personal_ids = list(personal_acc_result.scalars().all())

        first = datetime(y, m, 1, tzinfo=timezone.utc)
        next_m = m + 1 if m < 12 else 1
        next_y = y if m < 12 else y + 1
        first_next = datetime(next_y, next_m, 1, tzinfo=timezone.utc)

        inc_q = select(func.sum(Transaction.amount)).where(
            Transaction.bank_account_id.in_(personal_ids),
            Transaction.transaction_type == "income",
            Transaction.transaction_date >= first,
            Transaction.transaction_date < first_next,
        )
        if currency:
            inc_q = inc_q.where(Transaction.currency == currency)
        inc_r = await db.execute(inc_q)
        income = float(inc_r.scalar() or 0)

        hogar_q = (
            select(func.sum(Transaction.amount))
            .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
            .where(
                Transaction.household_id == household_id,
                Transaction.transaction_type == "expense",
                TransactionSplit.split_type == "shared",
                Transaction.transaction_date >= first,
                Transaction.transaction_date < first_next,
            )
        )
        if currency:
            hogar_q = hogar_q.where(Transaction.currency == currency)
        hogar_r = await db.execute(hogar_q)
        hogar_spent = float(hogar_r.scalar() or 0)

        personal_q = (
            select(func.sum(Transaction.amount))
            .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
            .where(
                Transaction.bank_account_id.in_(personal_ids),
                Transaction.transaction_type == "expense",
                TransactionSplit.split_type == "personal",
                Transaction.transaction_date >= first,
                Transaction.transaction_date < first_next,
            )
        )
        if currency:
            personal_q = personal_q.where(Transaction.currency == currency)
        personal_r = await db.execute(personal_q)
        personal_spent = float(personal_r.scalar() or 0)

        monthly_data.append(
            {"income": income, "hogar_spent": hogar_spent, "personal_spent": personal_spent}
        )

    historical = compute_historical_suggestion(monthly_data)

    return {
        "month": month.isoformat(),
        "allocation": allocation_block,
        "suggestions": {
            "historical": historical,
            "recommended": {**DEFAULT_ALLOCATION, "label": RECOMMENDED_LABEL},
        },
    }


async def upsert_allocation(
    db: AsyncSession,
    household_id: uuid.UUID,
    month: date,
    hogar_pct: float,
    ahorro_pct: float,
    personal_pct: float,
) -> dict:
    result = await db.execute(
        select(HouseholdBudgetAllocation).where(
            HouseholdBudgetAllocation.household_id == household_id,
            HouseholdBudgetAllocation.month == month,
        )
    )
    alloc = result.scalar_one_or_none()
    if alloc:
        alloc.hogar_pct = hogar_pct
        alloc.ahorro_pct = ahorro_pct
        alloc.personal_pct = personal_pct
    else:
        alloc = HouseholdBudgetAllocation(
            household_id=household_id,
            month=month,
            hogar_pct=hogar_pct,
            ahorro_pct=ahorro_pct,
            personal_pct=personal_pct,
        )
        db.add(alloc)
    await db.commit()
    return {
        "hogar_pct": hogar_pct,
        "ahorro_pct": ahorro_pct,
        "personal_pct": personal_pct,
        "is_default": False,
    }
