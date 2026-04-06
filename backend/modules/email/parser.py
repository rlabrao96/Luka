import re
from datetime import datetime, timezone
from modules.email.base import ParsedEmail


def _strip_html(html: str) -> str:
    """Strip HTML tags, style/script blocks, and collapse whitespace."""
    text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&#\d+;", "", text)
    text = re.sub(r"&[a-z]+;", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# --- Amount patterns ---
# US format: $17.08 (dot = decimal, comma = thousands) → stored as cents (1708)
# CLP format: $15.990 (dot = thousands, no decimals) → stored as integer (15990)
_US_AMOUNT_PATTERNS = [
    r"Amount:?\s*\$\s*([\d,]+\.\d{2})\b",  # Amount: $17.08 or Amount: $1,234.56
    r"payment of \$\s*([\d,]+\.\d{2})\b",  # Zelle® payment of $2,000.00
]
_CLP_AMOUNT_PATTERNS = [
    r"por\s+\$\s*([\d\.]+)",  # por $15.990
    r"Monto(?:\s+transferido)?:?\s*\$?\s*([\d\.]+)",  # Monto: 15.990 or Monto transferido $ 8.226
    r"\$\s*([\d\.]+)",  # $15.990 or $ 15.990
]

# Transfer patterns — detect transfers and extract the counterparty name.
# Outgoing: Banco de Chile "transferencia de fondos a {NAME}, el dia..."
# Outgoing: Santander "Datos de destino Nombre {NAME} RUT"
# Incoming: Edwards "cliente {NAME} ha efectuado una transferencia"
_NAME_UPPER_START = r"[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ ]{2,60}"  # must start uppercase
_NAME_ANY = r"[A-ZÁÉÍÓÚÑa-záéíóúñ][A-ZÁÉÍÓÚÑa-záéíóúñ ]{2,60}"
_TRANSFER_PATTERNS = [
    # US — Zelle (BofA): "payment of $... to BENJAMIN BRAITHWAITE has been sent"
    r"payment of \$[\d,]+\.\d{2} to\s+([A-Z][A-Z ]{2,60}?)\s+has been sent",
    # US — Zelle (PNC): "You sent a Zelle® payment to RAFAEL LABRA OETTINGER"
    r"sent a Zelle.*?payment to\s+([A-Z][A-Z ]{2,60})",
    # US — Zelle (PNC): "received a Zelle® payment from JANE DOE"
    r"received a Zelle.*?payment from\s+([A-Z][A-Z ]{2,60})",
    # Incoming — "cliente {NAME} ha efectuado una transferencia" (Edwards)
    # Must be before outgoing prose patterns to avoid matching "a tu cuenta"
    rf"cliente\s+({_NAME_ANY}?)\s+ha efectuado una transferencia",
    # Outgoing — name in prose (uppercase start to skip "a tu cuenta con el")
    rf"transferencia de fondos a\s+({_NAME_UPPER_START}?)(?:\s*,|\s+el\s)",
    rf"transferencia a\s+({_NAME_UPPER_START}?)(?:\s*,|\s+el\s|\s+por\s)",
    # Outgoing — name in "Datos del Destinatario" table (Banco de Chile)
    rf"Datos del Destinatario\s+Nombre\s+({_NAME_ANY}?)\s+Rut",
    # Outgoing — name in "Datos de destino" table (Santander)
    rf"Datos de destino\s+Nombre\s+({_NAME_ANY}?)\s+RUT",
]

# US merchant patterns — BofA uses "Where: MERCHANT_NAME"
# Merchant names can be mixed case (Spotify), contain @ (BA@PENNPRETCAFE), etc.
_US_MERCHANT_PATTERNS = [
    r"Where:?\s+([A-Za-z0-9@][A-Za-z0-9 &\-/'.@#]{2,50}?)(?:\s+View|\s+If\b|\s*$)",
]

# Chilean merchant patterns — order matters, most specific first.
_CLP_MERCHANT_PATTERNS = [
    r"Comercio\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9 ]{2,40}?)(?:\s+Monto|\s*$)",  # Comercio SCOTIABANK CAE Monto
    r"Comercio:?\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9 ]{2,40})",  # Comercio: COPEC LAS CONDES
    r"en\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9 ]{2,40}?)\s+(?:SANTIAGO|CL|el\b)",  # en MERCHANT SANTIAGO CL el
    r"en\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9 ]{2,40}?)(?:\s+el\s+\d|$)",  # en MERCHANT el 10/03
    r"en\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9 ]{2,40})",  # en LIDER PROVI (fallback)
]

_MONTHS_EN = (
    r"(?:January|February|March|April|May|June|" r"July|August|September|October|November|December)"
)

_DATE_PATTERNS = [
    r"(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})",  # 13/03/2026 09:45:03
    r"(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})",  # 10/03/2026 14:32
    r"(\d{2}/\d{2}/\d{4})",  # 10/03/2026
    rf"({_MONTHS_EN}\s+\d{{1,2}},?\s+\d{{4}})",  # March 28, 2026
]


def _parse_amount(text: str) -> tuple[int, str] | tuple[None, None]:
    """Parse amount, returning (amount_int, currency).

    US format: $17.08 → (1708, "USD") — stored as cents
    CLP format: $15.990 → (15990, "CLP") — stored as integer
    """
    # Try US format first (has exactly 2 decimal places)
    for pattern in _US_AMOUNT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw = match.group(1).replace(",", "")
            try:
                return int(round(float(raw) * 100)), "USD"
            except ValueError:
                continue
    # Fall back to CLP format (dot = thousands separator)
    for pattern in _CLP_AMOUNT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw = match.group(1).replace(".", "").replace(",", "")
            try:
                return int(raw), "CLP"
            except ValueError:
                continue
    return None, None


def _parse_transfer_recipient(text: str) -> str | None:
    """Extract recipient name from transfer emails (e.g. Banco de Chile fund transfers)."""
    for pattern in _TRANSFER_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip().title()
    return None


def _parse_merchant(text: str) -> str | None:
    # Try US patterns first (more specific labels like "Where:")
    for pattern in _US_MERCHANT_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip().upper()
    # Fall back to Chilean patterns
    for pattern in _CLP_MERCHANT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip().upper()
    return None


_DATE_FORMATS = [
    "%d/%m/%Y %H:%M:%S",  # 13/03/2026 09:45:03
    "%d/%m/%Y %H:%M",  # 10/03/2026 14:32
    "%d/%m/%Y",  # 10/03/2026
    "%B %d, %Y",  # March 28, 2026
    "%B %d %Y",  # March 28 2026
]


def _parse_date(text: str) -> datetime | None:
    for pattern in _DATE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            raw = match.group(1).strip()
            for fmt in _DATE_FORMATS:
                try:
                    return datetime.strptime(raw, fmt)
                except ValueError:
                    continue
    return None


def parse_bank_email(raw_text: str) -> ParsedEmail | None:
    """Parse a bank email alert (Chilean or US). Returns None if not a transaction email."""
    # Strip HTML if the email body contains HTML tags
    if "<html" in raw_text.lower() or "<table" in raw_text.lower():
        text = _strip_html(raw_text)
    else:
        text = raw_text

    amount, currency = _parse_amount(text)
    if amount is None:
        return None

    # Try transfer patterns first (e.g. "transferencia de fondos a Juan Jose Lamarca")
    transfer_recipient = _parse_transfer_recipient(text)
    if transfer_recipient:
        merchant = transfer_recipient
        transaction_type = "transfer"
    else:
        merchant = _parse_merchant(text)
        transaction_type = "expense"

    if merchant is None:
        return None

    date = _parse_date(text)
    if date is None:
        date = datetime.now(timezone.utc)

    return ParsedEmail(
        amount=amount,
        raw_merchant=merchant,
        transaction_date=date,
        bank_name="unknown",
        transaction_type=transaction_type,
        currency=currency,
    )
