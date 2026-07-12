"""Shared month-boundary helpers (single source of truth — ST-11 / M14).

Several modules used to carry their own copy of month-bounds math; drift in
one copy silently misfiles transactions at month edges. All month math for
aggregates belongs here.

Timezone (M14): pass the view's ``currency`` and bounds are computed at
LOCAL midnight for that currency's home market, then converted to UTC
instants for querying timestamptz columns. Without it, a Chilean buying
dinner at 22:00 on the 31st lands in next month's budget (UTC is +3/+4h
ahead of Santiago). Currency is a proxy for the user's financial timezone —
good for LATAM's single-timezone-per-market reality; USD deliberately stays
UTC (US spans four timezones; picking one would be wrong for most users).
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

_CURRENCY_TZ = {
    "CLP": "America/Santiago",
    "CLF": "America/Santiago",
    "COP": "America/Bogota",
    "MXN": "America/Mexico_City",
    "PEN": "America/Lima",
    "BRL": "America/Sao_Paulo",
    "ARS": "America/Argentina/Buenos_Aires",
    "UYU": "America/Montevideo",
    "PYG": "America/Asuncion",
}


def tz_for_currency(currency: str | None) -> ZoneInfo:
    name = _CURRENCY_TZ.get((currency or "").upper())
    return ZoneInfo(name) if name else ZoneInfo("UTC")


def month_bounds_datetime(
    month: date, currency: str | None = None
) -> tuple[datetime, datetime, int]:
    """Return (first_day_dt, first_day_next_dt, days_in_month).

    Bounds are UTC instants of local midnight in the currency's home
    timezone (UTC when no currency given — legacy behavior).
    """
    tz = tz_for_currency(currency)
    first_day = datetime(month.year, month.month, 1, tzinfo=tz).astimezone(timezone.utc)
    if month.month == 12:
        next_year, next_month = month.year + 1, 1
    else:
        next_year, next_month = month.year, month.month + 1
    first_day_next = datetime(next_year, next_month, 1, tzinfo=tz).astimezone(timezone.utc)
    days_in_month = calendar.monthrange(month.year, month.month)[1]
    return first_day, first_day_next, days_in_month


def month_bounds_date(month: date) -> tuple[date, date]:
    first = date(month.year, month.month, 1)
    last = date(month.year, month.month, calendar.monthrange(month.year, month.month)[1])
    return first, last


def prior_month(month: date, offset: int) -> date:
    """Return the first-of-month `offset` calendar months before `month`."""
    m = month.month - offset
    y = month.year
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


def today_day_in_month(month: date, days_in_month: int, currency: str | None = None) -> int:
    """Current day-of-month (in the currency's local timezone), clamped to
    the month when viewing a past month."""
    today = datetime.now(tz_for_currency(currency)).date()
    if today.year == month.year and today.month == month.month:
        return min(today.day, days_in_month)
    # Historical month — treat as fully observed
    return days_in_month
