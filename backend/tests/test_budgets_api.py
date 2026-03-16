import pytest
from modules.budgets.service import get_budget_status


@pytest.mark.skip(reason="Requires live Supabase DATABASE_URL")
@pytest.mark.asyncio
async def test_budget_status_shows_remaining(db, mock_household, mock_user):
    from modules.households.models import BankAccount, HouseholdBudget
    from datetime import date

    account = BankAccount(
        household_id=mock_household.id,
        user_id=mock_user.id,
        bank_name="bci",
        account_type="joint",
    )
    db.add(account)
    await db.flush()

    budget = HouseholdBudget(
        household_id=mock_household.id,
        bank_account_id=account.id,
        month=date(2026, 3, 1),
        budgeted=500000,
    )
    db.add(budget)
    await db.commit()

    status = await get_budget_status(db, household_id=mock_household.id, month=date(2026, 3, 1))
    assert status["budgeted"] == 500000
    assert status["spent"] == 0
    assert status["available"] == 500000
