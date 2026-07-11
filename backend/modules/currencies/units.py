"""Single source of truth for currency unit scaling.

Luka stores every ``transactions.amount`` as a **signed integer in minor
units**: cents for 2-decimal currencies (USD, EUR, MXN, BRL, PEN, ...) and
whole units for zero-decimal currencies (CLP, COP, ...). Every ingestion path
(email, Plaid, Luka Connect) MUST scale through this module — a path that
stores raw major units silently breaks cross-source matching and renders
100× off after the frontend's minor→major conversion.

Notes on the set below:
* COP is ISO-4217 2-decimal on paper, but Colombian banking uses whole pesos
  in practice and Luka has always stored COP unscaled — changing it would
  corrupt existing data. Kept zero-decimal deliberately.
* CLF (UF) is a 4-decimal unit; it is NOT zero-decimal (a bug in earlier
  copies of this set — rounding UF to integers loses up to ~CLP 19.500).
  We approximate it as 2-decimal minor units, the closest fit to Luka's
  two-scale storage convention.
"""

from decimal import ROUND_HALF_UP, Decimal

ZERO_DECIMAL_CURRENCIES = frozenset({"CLP", "COP", "JPY", "KRW", "PYG", "VND"})

_CENT = Decimal("0.01")
_ONE = Decimal("1")


def is_zero_decimal(currency: str | None) -> bool:
    return (currency or "").upper() in ZERO_DECIMAL_CURRENCIES


def minor_units_per_major(currency: str | None) -> int:
    """100 for 2-decimal currencies, 1 for zero-decimal ones."""
    return 1 if is_zero_decimal(currency) else 100


def to_minor_units(amount, currency: str | None) -> int:
    """Scale a major-unit amount (Decimal/float/int/str) to signed integer
    minor units. Half-up rounding — never truncation."""
    d = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    scaled = d * minor_units_per_major(currency)
    return int(scaled.quantize(_ONE, rounding=ROUND_HALF_UP))


def to_major_units(amount, currency: str | None) -> Decimal:
    """Convert a stored minor-unit amount back to major units."""
    d = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    return d / minor_units_per_major(currency)


def major_unit_quantum(currency: str | None) -> Decimal:
    """Smallest payable step in MAJOR units: 1 for CLP/COP, 0.01 for USD/MXN/...

    Use as the quantize step for any major-unit money math (trip splits,
    settlements) so zero-decimal currencies never produce fractional pesos.
    """
    return _ONE if is_zero_decimal(currency) else _CENT


def format_major(minor_amount, currency: str | None) -> str:
    """Human-readable major-unit rendering of a stored minor-unit amount.

    Backend-side fallback for notification copy ("USD 27.43", "CLP 15000").
    Rich locale-aware formatting belongs to the frontend.
    """
    major = to_major_units(minor_amount, currency)
    if is_zero_decimal(currency):
        return f"{currency} {major.quantize(_ONE)}"
    return f"{currency} {major.quantize(_CENT)}"
