import re
from datetime import datetime, timezone
from modules.email.base import ParsedEmail


# Pattern set covers Santander, BCI, Banco de Chile common alert formats
_AMOUNT_PATTERNS = [
    r"\$\s*([\d\.]+)",  # $15.990 or $ 15.990
    r"Monto:?\s*\$?\s*([\d\.]+)",  # Monto: 15.990
    r"por\s+\$\s*([\d\.]+)",  # por $15.990
]

_MERCHANT_PATTERNS = [
    r"en\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9 ]{2,40})",  # en LIDER PROVI
    r"Comercio:?\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9 ]{2,40})",  # Comercio: COPEC
    r"en\s+([A-Z][A-Z0-9 ]{2,40})\n",  # en STARBUCKS\n
]

_DATE_PATTERNS = [
    r"(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})",  # 10/03/2026 14:32
    r"(\d{2}/\d{2}/\d{4})",  # 10/03/2026
]


def _parse_amount(text: str) -> int | None:
    for pattern in _AMOUNT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw = match.group(1).replace(".", "").replace(",", "")
            try:
                return int(raw)
            except ValueError:
                continue
    return None


def _parse_merchant(text: str) -> str | None:
    for pattern in _MERCHANT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip().upper()
    return None


def _parse_date(text: str) -> datetime | None:
    for pattern in _DATE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            raw = match.group(1).strip()
            for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
                try:
                    return datetime.strptime(raw, fmt)
                except ValueError:
                    continue
    return None


def parse_bank_email(raw_text: str) -> ParsedEmail | None:
    """Parse a Chilean bank email alert. Returns None if not a transaction email."""
    amount = _parse_amount(raw_text)
    if amount is None:
        return None

    merchant = _parse_merchant(raw_text)
    if merchant is None:
        return None

    date = _parse_date(raw_text)
    if date is None:
        date = datetime.now(timezone.utc)

    return ParsedEmail(
        amount=amount,
        raw_merchant=merchant,
        transaction_date=date,
        bank_name="unknown",  # set by provider after matching email_sender_pattern
    )
