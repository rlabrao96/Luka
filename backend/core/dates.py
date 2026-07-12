"""Shared month-boundary helpers (single source of truth — ST-11).

Several modules used to carry their own copy of month-bounds math; drift in
one copy silently misfiles transactions at month edges. All month math for
aggregates belongs here.

Timezone note (M14): bounds are computed in UTC today. When per-user
timezones land, add a tz parameter here — every consumer picks it up at once.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timezone


def month_bounds_datetime(month: date) -> tuple[datetime, datetime, int]:
    """Return (first_day_dt, first_day_next_dt, days_in_month) as UTC datetimes."""
    first_day = datetime(month.year, month.month, 1, tzinfo=timezone.utc)
    if month.month == 12:
        next_year, next_month = month.year + 1, 1
    else:
        next_year, next_month = month.year, month.month + 1
    first_day_next = datetime(next_year, next_month, 1, tzinfo=timezone.utc)
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


def today_day_in_month(month: date, days_in_month: int) -> int:
    """Current day-of-month clamped to the month if we're viewing a past month."""
    today = datetime.now(timezone.utc).date()
    if today.year == month.year and today.month == month.month:
        return min(today.day, days_in_month)
    # Historical month — treat as fully observed
    return days_in_month
