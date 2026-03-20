# backend/tests/test_fintoc_classifier.py
from datetime import datetime
from modules.fintoc.classifier import classify_movement, MovementClassification
from modules.fintoc.client import FintocTransaction


def _txn(
    amount: int,
    description: str = "SUPERMERCADO",
    fintoc_id: str = "f1",
    account_id: str = "acc1",
    counterparty_id: str | None = None,
) -> FintocTransaction:
    return FintocTransaction(
        id=fintoc_id,
        amount=amount,
        description=description,
        transaction_date=datetime(2026, 3, 10),
        account_id=account_id,
        counterparty_account_id=counterparty_id,
    )


# --- Income classification ---


def test_positive_amount_no_keywords_is_income():
    result = classify_movement(_txn(500000), household_fintoc_ids=[], all_movements=[])
    assert result.classification == MovementClassification.INCOME
    assert result.matched_fintoc_account_id is None


def test_negative_amount_no_match_is_expense():
    result = classify_movement(_txn(-45000), household_fintoc_ids=[], all_movements=[])
    assert result.classification == MovementClassification.EXPENSE
    assert result.matched_fintoc_account_id is None


# --- Transfer via counterparty ID ---


def test_outflow_with_counterparty_id_matching_household_is_transfer():
    result = classify_movement(
        _txn(-200000, counterparty_id="acc_joint"),
        household_fintoc_ids=["acc_joint"],
        all_movements=[],
    )
    assert result.classification == MovementClassification.TRANSFER
    assert result.matched_fintoc_account_id == "acc_joint"


def test_inflow_with_counterparty_id_matching_household_is_inbound_transfer_skip():
    result = classify_movement(
        _txn(200000, counterparty_id="acc_personal"),
        household_fintoc_ids=["acc_personal"],
        all_movements=[],
    )
    assert result.classification == MovementClassification.INBOUND_TRANSFER_SKIP
    assert result.matched_fintoc_account_id == "acc_personal"


# --- Transfer via keyword + amount symmetry fallback ---


def test_outflow_transferencia_keyword_with_symmetric_inbound_is_transfer():
    outflow = _txn(
        -150000, description="TRANSFERENCIA A CUENTA", account_id="acc1", fintoc_id="f_out"
    )
    inbound = _txn(
        150000, description="TRANSFERENCIA RECIBIDA", account_id="acc2", fintoc_id="f_in"
    )
    result = classify_movement(outflow, household_fintoc_ids=[], all_movements=[inbound])
    assert result.classification == MovementClassification.TRANSFER
    assert result.matched_fintoc_account_id == "acc2"  # sibling account_id


def test_outflow_transferencia_keyword_no_symmetric_match_is_expense():
    outflow = _txn(-150000, description="TRANSFERENCIA A TERCERO", account_id="acc1")
    result = classify_movement(outflow, household_fintoc_ids=[], all_movements=[])
    assert result.classification == MovementClassification.EXPENSE


def test_inflow_traspaso_keyword_with_symmetric_outbound_is_inbound_skip():
    inflow = _txn(80000, description="TRASPASO RECIBIDO", account_id="acc2", fintoc_id="f_in2")
    outbound = _txn(-80000, description="TRASPASO REALIZADO", account_id="acc1", fintoc_id="f_out2")
    result = classify_movement(inflow, household_fintoc_ids=[], all_movements=[outbound])
    assert result.classification == MovementClassification.INBOUND_TRANSFER_SKIP
    assert result.matched_fintoc_account_id == "acc1"
