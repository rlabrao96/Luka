from datetime import timezone
from modules.bank_connect.mapper import (
    is_inter_account_transfer,
    map_movement_to_transaction,
    normalize_description,
    dedup_key,
    parse_movement_date,
)


def test_normalize_description():
    assert normalize_description("  Compra STARBUCKS  SANTIAGO  ") == "compra starbucks santiago"
    assert normalize_description("Abono Api En Linea:775009764") == "abono api en linea:775009764"


def test_parse_movement_date_with_time():
    result = parse_movement_date("18-03-2026", "13:36")
    assert result.year == 2026
    assert result.month == 3
    assert result.day == 18
    assert result.hour == 13
    assert result.minute == 36
    assert result.tzinfo == timezone.utc


def test_parse_movement_date_without_time():
    result = parse_movement_date("25-12-2025")
    assert result.hour == 0
    assert result.minute == 0


def test_map_movement_basic():
    movement = {
        "date": "18-03-2026",
        "time": "13:36",
        "description": "Compra en STARBUCKS",
        "amount": -3500,
        "balance": 150000,
        "source": "account",
        "currency": "CLP",
        "accountNumber": "****7502",
        "accountName": "Cuenta Corriente",
    }
    result = map_movement_to_transaction(
        movement, user_id="uid", household_id="hid", bank_account_id="baid"
    )
    assert result["raw_merchant_name"] == "Compra en STARBUCKS"
    assert result["amount"] == -3500
    assert result["currency"] == "CLP"
    assert result["source_type"] == "connect"
    assert result["source"] == "connect"
    assert result["status"] == "settled"
    assert result["transaction_type"] == "expense"
    assert result["transaction_date"].year == 2026
    assert result["transaction_date"].month == 3
    assert result["transaction_date"].day == 18
    assert result["transaction_date"].hour == 13
    assert result["transaction_date"].minute == 36


def test_map_movement_income():
    movement = {
        "date": "18-03-2026",
        "description": "Deposito",
        "amount": 500000,
        "balance": 650000,
        "source": "account",
    }
    result = map_movement_to_transaction(
        movement, user_id="uid", household_id="hid", bank_account_id=None
    )
    assert result["transaction_type"] == "income"
    assert result["bank_account_id"] is None


def test_dedup_key_deterministic():
    key1 = dedup_key("18-03-2026", "compra starbucks", -3500, "baid")
    key2 = dedup_key("18-03-2026", "compra starbucks", -3500, "baid")
    assert key1 == key2
    assert isinstance(key1, str)
    assert len(key1) > 0


def test_dedup_key_different_inputs():
    key1 = dedup_key("18-03-2026", "compra starbucks", -3500, "baid")
    key2 = dedup_key("19-03-2026", "compra starbucks", -3500, "baid")
    assert key1 != key2


def test_is_inter_account_transfer_cc_payment():
    assert is_inter_account_transfer("Pago Tarjeta Visa ****5032")
    assert is_inter_account_transfer("PAGO TARJETA CMR")
    assert is_inter_account_transfer("Pago Tarjeta De Credito")
    assert is_inter_account_transfer("Pago Pesos TEF PAGO NORMAL")
    assert is_inter_account_transfer("Pago Pesos TEF")


def test_is_inter_account_transfer_own_account():
    # Banco de Chile intra-account moves use its own RUT (96571220-8)
    assert is_inter_account_transfer("Traspaso A 96571220-8 Dolar")
    assert is_inter_account_transfer("Traspaso De 96571220-8 Fmu")


def test_is_inter_account_transfer_person_not_transfer():
    # Person-to-person transfers are NOT inter-account → expense/income
    assert not is_inter_account_transfer("Traspaso A:Camila Chahuan")
    assert not is_inter_account_transfer("Traspaso De:Javier Jorge Guerraty Korner")
    assert not is_inter_account_transfer("Compra en STARBUCKS")
    assert not is_inter_account_transfer("Deposito")


def test_map_movement_cc_payment_is_transfer():
    movement = {
        "date": "07-04-2026",
        "time": "13:51",
        "description": "Pago Tarjeta Visa ****5032",
        "amount": -881210,
        "source": "account",
    }
    result = map_movement_to_transaction(
        movement, user_id="uid", household_id="hid", bank_account_id="baid"
    )
    assert result["transaction_type"] == "transfer"


def test_map_movement_person_transfer_is_expense():
    movement = {
        "date": "07-04-2026",
        "time": "13:47",
        "description": "Traspaso A:Camila Chahuan",
        "amount": -685000,
        "source": "account",
    }
    result = map_movement_to_transaction(
        movement, user_id="uid", household_id="hid", bank_account_id="baid"
    )
    assert result["transaction_type"] == "expense"
