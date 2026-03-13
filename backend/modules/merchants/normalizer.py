import re

_PREFIXES = re.compile(
    r"^(COMPRA|PAGO|CARGO|TRANSFERENCIA|TRF|DEBITO|CREDITO)\s+",
    re.IGNORECASE,
)

_LOCATION_SUFFIXES = re.compile(
    r"\s+(PROVI|PROVIDENCIA|LAS\s+CONDES|VITACURA|MAIPU|MAIPÚ|ÑUÑOA|"
    r"NUNOA|PUDAHUEL|QUILICURA|RECOLETA|SANTIAGO|CENTRAL|CENTRO|"
    r"NORTE|SUR|ORIENTE|PONIENTE)\s*$",
    re.IGNORECASE,
)


def normalize_merchant(raw: str) -> str:
    """
    Normalize a raw merchant name from a Chilean bank email.
    "COMPRA LIDER PROVIDENCIA" → "LIDER"
    "PAGO NETFLIX" → "NETFLIX"
    """
    s = raw.strip().upper()
    s = _PREFIXES.sub("", s)
    s = _LOCATION_SUFFIXES.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s
