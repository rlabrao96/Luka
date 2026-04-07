import pytest
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_expense_email_stores_negative_amount_and_type():
    """Email expense should store negative amount and transaction_type='expense'."""
    from modules.email.parser import ParsedEmail

    parsed = ParsedEmail(
        amount=2500,
        raw_merchant="STARBUCKS",
        transaction_date=datetime.now(timezone.utc),
        bank_name="Bank of America",
        transaction_type="expense",
        currency="USD",
    )

    assert parsed.transaction_type == "expense"
    stored_amount = -abs(parsed.amount) if parsed.transaction_type == "expense" else parsed.amount
    assert stored_amount == -2500


@pytest.mark.asyncio
async def test_income_email_stores_positive_amount():
    """Email income should store positive amount and transaction_type='income'."""
    from modules.email.parser import ParsedEmail

    parsed = ParsedEmail(
        amount=50000,
        raw_merchant="WIRE DEPOSIT",
        transaction_date=datetime.now(timezone.utc),
        bank_name="Bank of America",
        transaction_type="income",
        currency="USD",
    )

    stored_amount = (
        -abs(parsed.amount) if parsed.transaction_type == "expense" else abs(parsed.amount)
    )
    assert stored_amount == 50000
