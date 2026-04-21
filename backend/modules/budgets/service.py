import uuid
from datetime import date, datetime, timezone
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from modules.households.models import HouseholdBudget, BankAccount
from modules.transactions.models import Transaction, TransactionSplit


async def get_budget_status(
    db: AsyncSession,
    household_id: uuid.UUID,
    month: date,
    currency: str | None = None,
) -> dict:
    # Budgets are per bank_account, and each account has a single currency.
    # When a currency is supplied, restrict both budgeted and spent totals to
    # that currency — mixing CLP and USD produces meaningless totals.
    budget_query = (
        select(func.sum(HouseholdBudget.budgeted))
        .join(BankAccount, BankAccount.id == HouseholdBudget.bank_account_id)
        .where(
            HouseholdBudget.household_id == household_id,
            HouseholdBudget.month == month,
            BankAccount.account_type == "joint",
        )
    )
    if currency:
        budget_query = budget_query.where(BankAccount.currency == currency)
    budget_result = await db.execute(budget_query)
    total_budgeted = float(budget_result.scalar() or 0)

    first_day = datetime(month.year, month.month, 1, tzinfo=timezone.utc)
    next_month_year = month.year + 1 if month.month == 12 else month.year
    next_month_num = 1 if month.month == 12 else month.month + 1
    first_day_next = datetime(next_month_year, next_month_num, 1, tzinfo=timezone.utc)

    # Expenses are stored negative per Luka convention. Sum abs() of expense
    # amounts only — income and transfers must not count as "spent".
    spent_query = (
        select(func.coalesce(func.sum(func.abs(Transaction.amount)), 0))
        .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .where(
            Transaction.household_id == household_id,
            Transaction.transaction_type == "expense",
            TransactionSplit.split_type == "shared",
            Transaction.transaction_date >= first_day,
            Transaction.transaction_date < first_day_next,
        )
    )
    if currency:
        spent_query = spent_query.where(Transaction.currency == currency)
    spent_result = await db.execute(spent_query)
    total_spent = float(spent_result.scalar() or 0)

    return {
        "household_id": str(household_id),
        "month": month.isoformat(),
        "budgeted": total_budgeted,
        "spent": total_spent,
        "available": total_budgeted - total_spent,
        "percent_used": round((total_spent / total_budgeted * 100) if total_budgeted > 0 else 0, 1),
    }


async def set_monthly_budget(
    db: AsyncSession,
    household_id: uuid.UUID,
    bank_account_id: uuid.UUID,
    month: date,
    amount: float,
) -> HouseholdBudget:
    # Authorization: the caller's membership in household_id is already
    # verified by the router. Here we also verify the target bank account
    # belongs to that same household — otherwise any member could write a
    # budget row pointing at another household's account (IDOR on write).
    acc_check = await db.execute(
        select(BankAccount.id).where(
            BankAccount.id == bank_account_id,
            BankAccount.household_id == household_id,
        )
    )
    if acc_check.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="bank account not in this household")

    result = await db.execute(
        select(HouseholdBudget).where(
            HouseholdBudget.household_id == household_id,
            HouseholdBudget.bank_account_id == bank_account_id,
            HouseholdBudget.month == month,
        )
    )
    budget = result.scalar_one_or_none()
    if budget:
        budget.budgeted = amount
    else:
        budget = HouseholdBudget(
            household_id=household_id,
            bank_account_id=bank_account_id,
            month=month,
            budgeted=amount,
        )
        db.add(budget)
    await db.commit()
    await db.refresh(budget)
    return budget
