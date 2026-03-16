import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, literal
from modules.households.models import HouseholdBudget, BankAccount
from modules.transactions.models import Transaction, TransactionSplit


async def get_budget_status(
    db: AsyncSession,
    household_id: uuid.UUID,
    month: date,
) -> dict:
    # Sum all budgets for joint accounts this month
    budget_result = await db.execute(
        select(func.sum(HouseholdBudget.budgeted))
        .join(BankAccount, BankAccount.id == HouseholdBudget.bank_account_id)
        .where(
            HouseholdBudget.household_id == household_id,
            HouseholdBudget.month == month,
            BankAccount.account_type == "joint",
        )
    )
    total_budgeted = float(budget_result.scalar() or 0)

    # Sum all shared spending this month
    spent_result = await db.execute(
        select(func.sum(Transaction.amount))
        .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .where(
            Transaction.household_id == household_id,
            TransactionSplit.split_type == "shared",
            func.date_trunc("month", Transaction.transaction_date)
            == func.date_trunc("month", literal(month)),
        )
    )
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
    # Upsert: update if exists, insert if not
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
