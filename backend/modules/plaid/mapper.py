import re
from datetime import datetime, timezone
from decimal import Decimal


ACCOUNT_KIND_MAP = {
    ("depository", "checking"): "checking_account",
    ("depository", "savings"): "savings_account",
    ("credit", "credit card"): "credit_card",
    ("depository", "paypal"): "wallet",
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


# Currency scaling lives in modules.currencies.units — single source of truth.
from modules.currencies.units import to_minor_units  # noqa: E402


def _plaid_currency(plaid_tx) -> str:
    """Plaid's currency code, trying unofficial_currency_code before the USD fallback."""
    return (
        getattr(plaid_tx, "iso_currency_code", None)
        or getattr(plaid_tx, "unofficial_currency_code", None)
        or "USD"
    ).upper()


def luka_amount_from_plaid(plaid_tx) -> int:
    """Convert a Plaid-reported amount into Luka's signed, integer-scaled amount.

    Plaid reports outflows positive; Luka stores expenses/transfers negative and income positive.
    For zero-decimal currencies (CLP, COP, ...) amounts are stored as integer units.
    For two-decimal currencies (USD, EUR, ...) amounts are stored as integer cents.

    This helper owns the sign/scale convention so the added and modified code paths
    agree on the encoding.
    """
    return to_minor_units(-Decimal(str(plaid_tx.amount)), _plaid_currency(plaid_tx))


def resolve_raw_name(plaid_tx) -> str:
    """Resolve the display merchant name for a Plaid tx.

    Zelle person > CC issuer > merchant_name > name. Shared by the added and
    modified sync paths so a pending-update never reverts an enriched name.
    """
    full_name = plaid_tx.name or ""
    zelle_person = _extract_zelle_person(full_name)
    if zelle_person:
        return zelle_person
    if _is_cc_payment(full_name):
        return full_name.split(" DES:")[0].strip().title()
    return plaid_tx.merchant_name or plaid_tx.name or "Unknown"


def map_plaid_transaction(plaid_tx, bank_account_id: str, user_id: str, household_id: str) -> dict:
    """Map a Plaid transaction object to a Luka transaction dict.

    Sign convention: Plaid positive = outflow (expense), Luka negative = expense.
    So we multiply by -1.
    """
    plaid_amount = float(plaid_tx.amount)
    luka_amount = luka_amount_from_plaid(plaid_tx)

    # Derive transaction_type from Plaid's amount sign (before our flip).
    # Zero-amount rows (card verifications) are expenses, not phantom income.
    transaction_type = "expense" if plaid_amount >= 0 else "income"

    raw_name = resolve_raw_name(plaid_tx)

    # Status from pending flag
    status = "pending" if plaid_tx.pending else "settled"

    return {
        "user_id": user_id,
        "household_id": household_id,
        "bank_account_id": bank_account_id,
        "raw_merchant_name": raw_name,
        "amount": luka_amount,
        "currency": _plaid_currency(plaid_tx),
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
    """Check if Plaid transaction is an internal transfer (not person-to-person).

    Zelle/Venmo are categorized by Plaid as TRANSFER_IN/OUT but are real
    expenses/income to other people — not internal account transfers.
    Only flag as "transfer" for CC payments, loan payments, and account moves.
    """
    pfc = getattr(plaid_tx, "personal_finance_category", None)
    if not pfc:
        return False
    primary = getattr(pfc, "primary", "")
    if primary not in ("TRANSFER_IN", "TRANSFER_OUT", "LOAN_PAYMENTS"):
        return False

    # Exclude person-to-person payments (Zelle, Venmo, CashApp)
    name = (plaid_tx.name or "").lower()
    merchant = (plaid_tx.merchant_name or "").lower()
    p2p_keywords = ("zelle", "venmo", "cashapp", "cash app", "paypal")
    if any(kw in name or kw in merchant for kw in p2p_keywords):
        return False

    return True
