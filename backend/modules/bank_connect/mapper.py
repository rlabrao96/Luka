import hashlib
import re
from datetime import datetime, timezone
from decimal import Decimal

from modules.currencies.units import to_minor_units

# Patterns that identify inter-account movements (CC payments, same-bank transfers).
# These should always be marked as transaction_type="transfer" with no category.
# NOTE: person-to-person transfers ("Traspaso A:Name") are NOT in this list — they
# are expense/income based on direction.
_INTER_ACCOUNT_PATTERNS = [
    re.compile(r"pago\s+tarjeta", re.IGNORECASE),
    re.compile(r"pago\s+pesos\s+tef", re.IGNORECASE),
    # Own-account transfers use a RUT or account number instead of a person name.
    # Pattern: "Traspaso A <digits>-<digit>" or "Traspaso De <digits>-<digit>"
    re.compile(r"traspaso\s+(a|de)\s+\d{5,}-[\dk]", re.IGNORECASE),
]


def is_inter_account_transfer(description: str) -> bool:
    """Return True if the movement description matches a known inter-account pattern."""
    return any(p.search(description) for p in _INTER_ACCOUNT_PATTERNS)


def normalize_description(desc: str) -> str:
    """Normalize description for dedup comparison."""
    return " ".join(desc.strip().lower().split())


def dedup_key(date_str: str, normalized_desc: str, amount: float, bank_account_id: str) -> str:
    """Generate a dedup key from movement fields.

    The amount is canonicalized through Decimal so `1050` and `1050.0`
    (int vs float drift between scraper runs) hash identically.
    """
    canonical_amount = f"{Decimal(str(amount)).normalize():f}"
    raw = f"{date_str}|{normalized_desc}|{canonical_amount}|{bank_account_id}"
    return hashlib.sha256(raw.encode()).hexdigest()


def parse_movement_date(date_str: str, time_str: str | None = None) -> datetime:
    """Parse date string and optional HH:MM time into a timezone-aware datetime.

    Supports: dd-mm-yyyy, dd/mm/yyyy, yyyy-mm-dd, yyyy/mm/dd
    """
    hour, minute = (0, 0)
    if time_str:
        parts = time_str.split(":")
        hour, minute = int(parts[0]), int(parts[1])

    # Normalize separators
    cleaned = date_str.replace("/", "-")
    parts = cleaned.split("-")

    if len(parts) == 3:
        if len(parts[0]) == 4:
            # yyyy-mm-dd
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        else:
            # dd-mm-yyyy
            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
    else:
        # Fallback: try dateutil-style parsing
        from dateutil.parser import parse as dateutil_parse

        dt = dateutil_parse(date_str)
        return dt.replace(hour=hour, minute=minute, tzinfo=timezone.utc)

    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def map_movement_to_transaction(
    movement: dict,
    user_id: str,
    household_id: str,
    bank_account_id: str | None,
) -> dict:
    """Map a raw Luka Connect movement to transaction fields.

    Amounts are scaled to Luka's integer minor-unit convention (whole pesos
    for CLP/COP, cents for MXN/BRL/PEN/USD). Scrapers emit major units —
    storing them raw breaks cross-source matching and renders 100× off for
    2-decimal currencies.
    """
    description = movement["description"]
    currency = movement.get("currency", "CLP")
    amount = to_minor_units(movement["amount"], currency)

    # Inter-account movements (CC payments, same-bank own-account moves) → transfer
    if is_inter_account_transfer(description):
        tx_type = "transfer"
    else:
        tx_type = "expense" if amount < 0 else "income"

    return {
        "user_id": user_id,
        "household_id": household_id,
        "bank_account_id": bank_account_id,
        "raw_merchant_name": description,
        "amount": amount,
        "currency": currency,
        "transaction_date": parse_movement_date(movement["date"], movement.get("time")),
        "source": "connect",
        "source_type": "connect",
        "status": "settled",
        "transaction_type": tx_type,
    }
