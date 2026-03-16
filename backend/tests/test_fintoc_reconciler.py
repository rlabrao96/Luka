from datetime import datetime
from modules.fintoc.reconciler import find_match
from modules.fintoc.client import FintocTransaction


def make_fintoc_txn(amount, description, days_offset=0):
    from datetime import timedelta

    return FintocTransaction(
        id=f"ftc_{amount}",
        amount=amount,
        description=description,
        transaction_date=datetime(2026, 3, 10) + timedelta(days=days_offset),
        account_id="acc-1",
    )


def test_exact_match_on_amount_and_merchant():
    pending = [
        {
            "id": "txn-1",
            "amount": 15990,
            "raw_merchant_name": "LIDER PROVI",
            "transaction_date": datetime(2026, 3, 10),
        },
    ]
    ftc = make_fintoc_txn(15990, "COMPRA LIDER PROVIDENCIA")
    result = find_match(ftc, pending)
    assert result is not None
    assert result.transaction_id == "txn-1"
    assert result.confidence >= 0.7


def test_no_match_on_wrong_amount():
    pending = [
        {
            "id": "txn-1",
            "amount": 20000,
            "raw_merchant_name": "LIDER PROVI",
            "transaction_date": datetime(2026, 3, 10),
        },
    ]
    ftc = make_fintoc_txn(15990, "LIDER")
    result = find_match(ftc, pending)
    assert result is None


def test_match_within_3_day_window():
    pending = [
        {
            "id": "txn-1",
            "amount": 32000,
            "raw_merchant_name": "COPEC",
            "transaction_date": datetime(2026, 3, 8),
        },
    ]
    ftc = make_fintoc_txn(32000, "COPEC LAS CONDES", days_offset=2)  # 2 days later
    result = find_match(ftc, pending)
    assert result is not None


def test_no_match_outside_3_day_window():
    pending = [
        {
            "id": "txn-1",
            "amount": 32000,
            "raw_merchant_name": "COPEC",
            "transaction_date": datetime(2026, 3, 1),
        },
    ]
    ftc = make_fintoc_txn(32000, "COPEC", days_offset=9)  # 9 days later
    result = find_match(ftc, pending)
    assert result is None
