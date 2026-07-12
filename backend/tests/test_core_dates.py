"""core/dates timezone-aware month bounds (M14)."""

from datetime import date, datetime, timezone

from core.dates import month_bounds_datetime, prior_month, tz_for_currency


def test_clp_month_bounds_are_santiago_midnight():
    first, first_next, days = month_bounds_datetime(date(2026, 7, 1), "CLP")
    # Santiago is UTC-4 in July (winter) → local midnight = 04:00 UTC.
    assert first == datetime(2026, 7, 1, 4, 0, tzinfo=timezone.utc)
    assert first_next == datetime(2026, 8, 1, 4, 0, tzinfo=timezone.utc)
    assert days == 31


def test_late_night_purchase_stays_in_local_month():
    """A Chilean dinner at 23:00 local on Jul 31 (03:00 UTC Aug 1) must fall
    INSIDE July's bounds — the exact bug UTC bounds had."""
    first, first_next, _ = month_bounds_datetime(date(2026, 7, 1), "CLP")
    dinner_utc = datetime(2026, 8, 1, 3, 0, tzinfo=timezone.utc)  # Jul 31 23:00 CLT
    assert first <= dinner_utc < first_next


def test_usd_stays_utc():
    first, _, _ = month_bounds_datetime(date(2026, 7, 1), "USD")
    assert first == datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)


def test_no_currency_is_legacy_utc():
    first, _, _ = month_bounds_datetime(date(2026, 7, 1))
    assert first == datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)


def test_tz_mapping_and_prior_month():
    assert str(tz_for_currency("BRL")) == "America/Sao_Paulo"
    assert str(tz_for_currency("XXX")) == "UTC"
    assert prior_month(date(2026, 2, 1), 3) == date(2025, 11, 1)
