from datetime import datetime, timezone


ACCOUNT_KIND_MAP = {
    ("depository", "checking"): "checking_account",
    ("depository", "savings"): "savings_account",
    ("credit", "credit card"): "credit_card",
}


def map_account_kind(plaid_type: str, plaid_subtype: str | None) -> str:
    return ACCOUNT_KIND_MAP.get((plaid_type, plaid_subtype), "other")


def map_plaid_transaction(plaid_tx, bank_account_id: str, user_id: str, household_id: str) -> dict:
    """Map a Plaid transaction object to a Luka transaction dict.

    Sign convention: Plaid positive = outflow (expense), Luka negative = expense.
    So we multiply by -1.
    """
    plaid_amount = float(plaid_tx.amount)
    luka_amount = plaid_amount * -1

    # Derive transaction_type from Plaid's amount sign (before our flip)
    transaction_type = "expense" if plaid_amount > 0 else "income"

    # Use merchant_name if available, fall back to name
    raw_name = plaid_tx.merchant_name or plaid_tx.name or "Unknown"

    # Status from pending flag
    status = "pending" if plaid_tx.pending else "confirmed"

    return {
        "user_id": user_id,
        "household_id": household_id,
        "bank_account_id": bank_account_id,
        "raw_merchant_name": raw_name,
        "amount": luka_amount,
        "currency": plaid_tx.iso_currency_code or "USD",
        "transaction_date": datetime.combine(plaid_tx.date, datetime.min.time()).replace(
            tzinfo=timezone.utc
        ),
        "source": "plaid",
        "source_type": "plaid",
        "status": status,
        "transaction_type": transaction_type,
        "plaid_transaction_id": plaid_tx.transaction_id,
    }


def is_plaid_transfer(plaid_tx) -> bool:
    """Check if Plaid's personal_finance_category indicates a transfer."""
    pfc = getattr(plaid_tx, "personal_finance_category", None)
    if not pfc:
        return False
    primary = getattr(pfc, "primary", "")
    return primary in ("TRANSFER_IN", "TRANSFER_OUT", "LOAN_PAYMENTS")
