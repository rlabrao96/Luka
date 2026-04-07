from datetime import date
from decimal import Decimal
from modules.subscriptions.service import detect_from_rows, predict_next_date


def test_detect_from_rows_finds_recurring():
    """Merchant appearing in 2+ consecutive months is detected."""
    rows = [
        {
            "merchant_key": "Netflix",
            "category": "Streaming",
            "amount": Decimal("13500"),
            "tx_date": date(2026, 3, 8),
            "month": "2026-03",
            "split_type": "personal",
            "currency": "CLP",
        },
        {
            "merchant_key": "Netflix",
            "category": "Streaming",
            "amount": Decimal("12000"),
            "tx_date": date(2026, 2, 8),
            "month": "2026-02",
            "split_type": "personal",
            "currency": "CLP",
        },
    ]
    result = detect_from_rows(rows)
    assert len(result) == 1
    assert result[0]["merchant_name"] == "Netflix"
    assert result[0]["trend"] == "increased"
    assert result[0]["months_seen"] == 2


def test_detect_from_rows_skips_non_consecutive():
    """Merchant appearing in non-consecutive months is NOT detected."""
    rows = [
        {
            "merchant_key": "Random Shop",
            "category": "Compras",
            "amount": Decimal("10000"),
            "tx_date": date(2026, 3, 5),
            "month": "2026-03",
            "split_type": "personal",
            "currency": "CLP",
        },
        {
            "merchant_key": "Random Shop",
            "category": "Compras",
            "amount": Decimal("10000"),
            "tx_date": date(2026, 1, 5),
            "month": "2026-01",
            "split_type": "personal",
            "currency": "CLP",
        },
    ]
    result = detect_from_rows(rows)
    assert len(result) == 0


def test_detect_from_rows_amount_tolerance():
    """Amounts within 20% are accepted; beyond 20% rejected."""
    rows_ok = [
        {
            "merchant_key": "Gym",
            "category": "Deporte",
            "amount": Decimal("12000"),
            "tx_date": date(2026, 3, 1),
            "month": "2026-03",
            "split_type": "shared",
            "currency": "CLP",
        },
        {
            "merchant_key": "Gym",
            "category": "Deporte",
            "amount": Decimal("14000"),
            "tx_date": date(2026, 2, 1),
            "month": "2026-02",
            "split_type": "shared",
            "currency": "CLP",
        },
    ]
    assert len(detect_from_rows(rows_ok)) == 1

    rows_bad = [
        {
            "merchant_key": "Gym",
            "category": "Deporte",
            "amount": Decimal("12000"),
            "tx_date": date(2026, 3, 1),
            "month": "2026-03",
            "split_type": "shared",
            "currency": "CLP",
        },
        {
            "merchant_key": "Gym",
            "category": "Deporte",
            "amount": Decimal("20000"),
            "tx_date": date(2026, 2, 1),
            "month": "2026-02",
            "split_type": "shared",
            "currency": "CLP",
        },
    ]
    assert len(detect_from_rows(rows_bad)) == 0


def test_predict_next_date_normal():
    assert predict_next_date(date(2026, 3, 15)) == date(2026, 4, 15)


def test_predict_next_date_month_end():
    """Jan 31 -> Feb 28 (2026 is not a leap year)."""
    assert predict_next_date(date(2026, 1, 31)) == date(2026, 2, 28)


def test_detect_from_rows_includes_currency():
    """Each detected subscription includes the currency from the latest transaction."""
    rows = [
        {
            "merchant_key": "Netflix",
            "category": "Streaming",
            "amount": Decimal("1350"),
            "tx_date": date(2026, 3, 8),
            "month": "2026-03",
            "split_type": "personal",
            "currency": "USD",
        },
        {
            "merchant_key": "Netflix",
            "category": "Streaming",
            "amount": Decimal("1350"),
            "tx_date": date(2026, 2, 8),
            "month": "2026-02",
            "split_type": "personal",
            "currency": "USD",
        },
    ]
    result = detect_from_rows(rows)
    assert len(result) == 1
    assert result[0]["currency"] == "USD"
    assert result[0]["next_charge_day"] == 8
    assert "predicted_next_date" not in result[0]


def test_detect_from_rows_recent_charges():
    """Recent charges returns last 3 transactions sorted newest first."""
    rows = [
        {
            "merchant_key": "Gym",
            "category": "Deporte",
            "amount": Decimal("12000"),
            "tx_date": date(2026, 4, 1),
            "month": "2026-04",
            "split_type": "personal",
            "currency": "CLP",
        },
        {
            "merchant_key": "Gym",
            "category": "Deporte",
            "amount": Decimal("12000"),
            "tx_date": date(2026, 3, 1),
            "month": "2026-03",
            "split_type": "personal",
            "currency": "CLP",
        },
        {
            "merchant_key": "Gym",
            "category": "Deporte",
            "amount": Decimal("11500"),
            "tx_date": date(2026, 2, 1),
            "month": "2026-02",
            "split_type": "personal",
            "currency": "CLP",
        },
    ]
    result = detect_from_rows(rows)
    assert len(result) == 1
    charges = result[0]["recent_charges"]
    assert len(charges) == 3
    assert charges[0]["date"] == date(2026, 4, 1)
    assert charges[0]["amount"] == Decimal("12000")
