import hashlib
from datetime import datetime, timezone


def normalize_description(desc: str) -> str:
    """Normalize description for dedup comparison."""
    return " ".join(desc.strip().lower().split())


def dedup_key(date_str: str, normalized_desc: str, amount: float, bank_account_id: str) -> str:
    """Generate a dedup key from movement fields."""
    raw = f"{date_str}|{normalized_desc}|{amount}|{bank_account_id}"
    return hashlib.sha256(raw.encode()).hexdigest()


def parse_movement_date(date_str: str, time_str: str | None = None) -> datetime:
    """Parse dd-mm-yyyy date and optional HH:MM time into a timezone-aware datetime."""
    day, month, year = date_str.split("-")
    hour, minute = (0, 0)
    if time_str:
        parts = time_str.split(":")
        hour, minute = int(parts[0]), int(parts[1])
    return datetime(int(year), int(month), int(day), hour, minute, tzinfo=timezone.utc)


def map_movement_to_transaction(
    movement: dict,
    user_id: str,
    household_id: str,
    bank_account_id: str | None,
) -> dict:
    """Map a raw Luka Connect movement to transaction fields."""
    return {
        "user_id": user_id,
        "household_id": household_id,
        "bank_account_id": bank_account_id,
        "raw_merchant_name": movement["description"],
        "amount": movement["amount"],
        "currency": movement.get("currency", "CLP"),
        "transaction_date": parse_movement_date(movement["date"], movement.get("time")),
        "source": "connect",
        "source_type": "connect",
        "status": "settled",
        "transaction_type": "expense" if movement["amount"] < 0 else "income",
    }
