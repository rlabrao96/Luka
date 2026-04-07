import re
from datetime import datetime, timezone


ACCOUNT_KIND_MAP = {
    ("depository", "checking"): "checking_account",
    ("depository", "savings"): "savings_account",
    ("credit", "credit card"): "credit_card",
}

# Zelle patterns: extract person name
_ZELLE_PERSON_RE = re.compile(
    r"zelle\s+(?:payment|transfer)\s+(?:to|from)\s+" r"([A-Z][A-Za-z'-]+(?: [A-Z][A-Za-z'-]+)+)",
    re.IGNORECASE,
)
_ZELLE_TRAILING_RE = re.compile(
    r"zelle\s+transfer\s+conf#\s*\S+;\s*(.+)",
    re.IGNORECASE,
)

# Credit card payment patterns (ACH from BofA to card issuers)
_CC_PAYMENT_PATTERNS = [
    re.compile(r"AMERICAN EXPRESS\s+DES:ACH PMT", re.IGNORECASE),
    re.compile(r"CHASE\s+DES:EPAY", re.IGNORECASE),
    re.compile(r"DISCOVER\s+DES:E-PAYMENT", re.IGNORECASE),
    re.compile(r"CAPITAL ONE\s+DES:", re.IGNORECASE),
]


def _extract_zelle_person(name: str) -> str | None:
    """Extract person name from Zelle transaction descriptions."""
    m = _ZELLE_PERSON_RE.search(name)
    if m:
        return m.group(1).strip().title()
    m = _ZELLE_TRAILING_RE.search(name)
    if m:
        return m.group(1).strip().title()
    return None


def _is_cc_payment(name: str) -> bool:
    """Check if transaction is a credit card bill payment."""
    return any(p.search(name) for p in _CC_PAYMENT_PATTERNS)


def map_account_kind(plaid_type, plaid_subtype) -> str:
    return ACCOUNT_KIND_MAP.get((str(plaid_type), str(plaid_subtype)), "other")


def map_plaid_transaction(plaid_tx, bank_account_id: str, user_id: str, household_id: str) -> dict:
    """Map a Plaid transaction object to a Luka transaction dict.

    Sign convention: Plaid positive = outflow (expense), Luka negative = expense.
    So we multiply by -1.
    """
    plaid_amount = float(plaid_tx.amount)
    # Plaid sends dollars; Luka stores USD as cents (frontend divides by 100)
    luka_amount = round(plaid_amount * -100)

    # Derive transaction_type from Plaid's amount sign (before our flip)
    transaction_type = "expense" if plaid_amount > 0 else "income"

    # Full description (name has more detail than merchant_name for Zelle/ACH)
    full_name = plaid_tx.name or ""

    # Extract person name from Zelle transactions
    zelle_person = _extract_zelle_person(full_name)
    if zelle_person:
        raw_name = zelle_person
    elif _is_cc_payment(full_name):
        # Credit card payments → use issuer name, mark as transfer
        raw_name = full_name.split(" DES:")[0].strip().title()
        transaction_type = "transfer"
    else:
        # Default: prefer merchant_name, fall back to name
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
