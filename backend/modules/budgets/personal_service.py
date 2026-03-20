# backend/modules/budgets/personal_service.py
import uuid
import calendar
from datetime import date, datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from modules.transactions.models import Transaction, TransactionSplit
from modules.households.models import BankAccount, HouseholdBudgetAllocation, Household


def compute_personal_ceiling(
    income: float,
    user_deposited: float,
    personal_pct: float | None,
    allocation_exists: bool,
    mode: str,
) -> float:
    if allocation_exists and personal_pct is not None:
        return income * personal_pct / 100
    if mode == "waterfall":
        return income - user_deposited
    return income  # single mode


def build_personal_block(
    ceiling: float,
    spent: float,
    breakdown_household: float,
    breakdown_personal: float,
) -> dict:
    clamped = ceiling < 0
    available = ceiling - spent if not clamped else -spent
    pct_used = round(spent / ceiling * 100, 1) if ceiling > 0 else None
    return {
        "ceiling": ceiling,
        "ceiling_clamped": clamped,
        "spent": spent,
        "breakdown": {
            "household": breakdown_household,
            "personal": breakdown_personal,
        },
        "available": available,
        "percent_used": pct_used,
    }


def compute_pace(
    spendable_budget: float,
    daily_cumulative: dict[int, float],
    today_day: int,
    days_in_month: int,
) -> dict:
    pace_at_today = spendable_budget * today_day / days_in_month if days_in_month > 0 else 0
    actual_at_today = daily_cumulative.get(today_day, 0.0)
    delta = actual_at_today - pace_at_today
    daily_points = [
        {"day": d, "cumulative_spent": daily_cumulative.get(d, 0.0)}
        for d in range(1, today_day + 1)
    ]
    return {
        "spendable_budget": spendable_budget,
        "daily_points": daily_points,
        "today_day": today_day,
        "days_in_month": days_in_month,
        "pace_at_today": round(pace_at_today, 0),
        "actual_at_today": actual_at_today,
        "delta": round(delta, 0),
        "on_track": delta <= 0,
    }


async def get_personal_budget(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    month: date,
) -> dict:
    first_day = datetime(month.year, month.month, 1, tzinfo=timezone.utc)
    last_day_num = calendar.monthrange(month.year, month.month)[1]
    next_month_year = month.year + 1 if month.month == 12 else month.year
    next_month_num = 1 if month.month == 12 else month.month + 1
    first_day_next = datetime(next_month_year, next_month_num, 1, tzinfo=timezone.utc)
    today = datetime.now(timezone.utc)
    today_day = (
        min(today.day, last_day_num)
        if today.year == month.year and today.month == month.month
        else last_day_num
    )

    # Mode detection
    household = await db.get(Household, household_id)
    mode = "single" if household.type == "individual" else "waterfall"

    # Allocation
    alloc_result = await db.execute(
        select(HouseholdBudgetAllocation).where(
            HouseholdBudgetAllocation.household_id == household_id,
            HouseholdBudgetAllocation.month == month,
        )
    )
    allocation = alloc_result.scalar_one_or_none()
    alloc_exists = allocation is not None
    ahorro_pct = float(allocation.ahorro_pct) if allocation else 20.0
    personal_pct = float(allocation.personal_pct) if allocation else 30.0

    # Income — requesting user's personal accounts
    personal_account_ids_result = await db.execute(
        select(BankAccount.id).where(
            BankAccount.user_id == user_id,
            BankAccount.household_id == household_id,
            BankAccount.account_type == "personal",
            BankAccount.is_active.is_(True),
        )
    )
    personal_account_ids = list(personal_account_ids_result.scalars().all())

    income_result = await db.execute(
        select(func.sum(Transaction.amount)).where(
            Transaction.bank_account_id.in_(personal_account_ids),
            Transaction.transaction_type == "income",
            Transaction.transaction_date >= first_day,
            Transaction.transaction_date < first_day_next,
        )
    )
    income = float(income_result.scalar() or 0)

    # User's own deposits to joint (for ceiling when no allocation)
    user_deposited_result = await db.execute(
        select(func.sum(Transaction.amount)).where(
            Transaction.bank_account_id.in_(personal_account_ids),
            Transaction.transaction_type == "transfer",
            Transaction.transaction_date >= first_day,
            Transaction.transaction_date < first_day_next,
        )
    )
    user_deposited = float(user_deposited_result.scalar() or 0)

    # Household block (waterfall only)
    household_block = None
    if mode == "waterfall":
        # Total deposits from all members to joint
        all_member_accounts_result = await db.execute(
            select(BankAccount.id).where(
                BankAccount.household_id == household_id,
                BankAccount.account_type == "personal",
                BankAccount.is_active.is_(True),
            )
        )
        all_personal_ids = list(all_member_accounts_result.scalars().all())

        total_deposited_result = await db.execute(
            select(func.sum(Transaction.amount)).where(
                Transaction.bank_account_id.in_(all_personal_ids),
                Transaction.transaction_type == "transfer",
                Transaction.transaction_date >= first_day,
                Transaction.transaction_date < first_day_next,
            )
        )
        total_deposited = float(total_deposited_result.scalar() or 0)

        # Household spending (shared splits on any account in household)
        household_spent_result = await db.execute(
            select(func.sum(Transaction.amount))
            .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
            .where(
                Transaction.household_id == household_id,
                Transaction.transaction_date >= first_day,
                Transaction.transaction_date < first_day_next,
                TransactionSplit.split_type == "shared",
                Transaction.transaction_type == "expense",
            )
        )
        household_spent = float(household_spent_result.scalar() or 0)

        if total_deposited > 0:
            household_block = {
                "deposited": total_deposited,
                "spent": household_spent,
                "available": total_deposited - household_spent,
                "percent_used": round(household_spent / total_deposited * 100, 1),
            }
        else:
            household_block = {
                "deposited": None,
                "spent": household_spent,
                "available": None,
                "percent_used": None,
            }

    # Personal spending breakdown
    personal_shared_result = await db.execute(
        select(func.sum(Transaction.amount))
        .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .where(
            Transaction.bank_account_id.in_(personal_account_ids),
            Transaction.transaction_type == "expense",
            TransactionSplit.split_type == "shared",
            Transaction.transaction_date >= first_day,
            Transaction.transaction_date < first_day_next,
        )
    )
    breakdown_household = float(personal_shared_result.scalar() or 0)

    personal_only_result = await db.execute(
        select(func.sum(Transaction.amount))
        .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .where(
            Transaction.bank_account_id.in_(personal_account_ids),
            Transaction.transaction_type == "expense",
            TransactionSplit.split_type == "personal",
            Transaction.transaction_date >= first_day,
            Transaction.transaction_date < first_day_next,
        )
    )
    breakdown_personal = float(personal_only_result.scalar() or 0)

    ceiling = compute_personal_ceiling(income, user_deposited, personal_pct, alloc_exists, mode)
    personal_block = build_personal_block(
        ceiling=ceiling,
        spent=breakdown_household + breakdown_personal,
        breakdown_household=breakdown_household,
        breakdown_personal=breakdown_personal,
    )

    # Pace
    all_spending_result = await db.execute(
        select(
            func.date_part("day", Transaction.transaction_date).label("day"),
            func.sum(Transaction.amount).label("total"),
        )
        .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .where(
            Transaction.bank_account_id.in_(personal_account_ids),
            Transaction.transaction_type == "expense",
            Transaction.transaction_date >= first_day,
            Transaction.transaction_date < first_day_next,
        )
        .group_by(func.date_part("day", Transaction.transaction_date))
    )
    daily_raw = {int(row.day): float(row.total) for row in all_spending_result}

    # Build cumulative
    cumulative: dict[int, float] = {}
    running = 0.0
    for d in range(1, today_day + 1):
        running += daily_raw.get(d, 0.0)
        cumulative[d] = running

    spendable = income * (1 - ahorro_pct / 100)
    pace_block = compute_pace(
        spendable_budget=spendable,
        daily_cumulative=cumulative,
        today_day=today_day,
        days_in_month=last_day_num,
    )

    response = {
        "mode": mode,
        "month": month.isoformat(),
        "income": income,
        "personal": personal_block,
        "pace": pace_block,
    }
    if household_block is not None:
        response["household"] = household_block

    return response
