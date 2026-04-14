"""Single source of truth for which transaction categories are 'savings-equivalent'.

Transactions in these categories are excluded from `spendable.spent`
and counted toward `savings_target.progress`. See spec §5.4.

Normalization: `is_savings_category` strips, lowercases, and removes
common accents so new contributors can add `"Inversión"`, `"APV"`,
`"Ahorro"` in any natural casing without introducing near-duplicates.
"""

SAVINGS_EQUIVALENT_CATEGORIES: frozenset[str] = frozenset(
    {
        "inversion",
        "ahorro",
        "apv",
    }
)


def _normalize(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
    )


def is_savings_category(category: str | None) -> bool:
    if not category:
        return False
    return _normalize(category) in SAVINGS_EQUIVALENT_CATEGORIES
