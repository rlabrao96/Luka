import json
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from modules.whatsapp.handler import handle_text_message, parse_manual_expense
from modules.whatsapp.session import _session_key, _normalize_phone


def _make_redis(stored: dict) -> AsyncMock:
    mock = AsyncMock()

    async def mock_setex(key, ttl, val):
        stored[key] = val

    async def mock_get(key):
        return stored.get(key)

    async def mock_delete(*keys):
        for k in keys:
            stored.pop(k, None)

    mock.setex = mock_setex
    mock.get = mock_get
    mock.delete = mock_delete
    return mock


@pytest.mark.asyncio
async def test_handle_text_message_updates_merchant():
    """When step is awaiting_new_merchant, updates raw_merchant_name and re-sends alert."""
    stored = {}
    phone = "56912345678"
    txn_id = "txn-abc"

    # Pre-populate active_edit and session
    stored[f"wa_active_edit:{phone}"] = txn_id
    stored[_session_key(phone, txn_id)] = json.dumps({
        "transaction_id": txn_id,
        "step": "awaiting_new_merchant",
        "split_type": "",
        "raw_merchant": "OldName",
        "overflow_categories": [],
    })

    redis = _make_redis(stored)

    mock_txn = MagicMock()
    mock_txn.id = txn_id
    mock_txn.raw_merchant_name = "OldName"
    mock_txn.amount = 5000
    mock_txn.currency = "CLP"
    mock_txn.bank_account_id = None

    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none = MagicMock(return_value=mock_txn)
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_execute_result)

    with patch("modules.whatsapp.handler.send_expense_alert", new_callable=AsyncMock, return_value="wamid.NEW") as mock_alert, \
         patch("modules.whatsapp.handler.get_user_ranked_categories", new_callable=AsyncMock, return_value=["Restaurantes"]):
        await handle_text_message(phone=phone, text="NewName", db=mock_db, redis=redis)

    assert mock_txn.raw_merchant_name == "NewName"
    mock_alert.assert_called_once()
    # active_edit should be cleared
    assert f"wa_active_edit:{phone}" not in stored


@pytest.mark.asyncio
async def test_handle_text_message_updates_amount():
    """When step is awaiting_new_amount, parses int and updates txn.amount."""
    stored = {}
    phone = "56912345678"
    txn_id = "txn-xyz"

    stored[f"wa_active_edit:{phone}"] = txn_id
    stored[_session_key(phone, txn_id)] = json.dumps({
        "transaction_id": txn_id,
        "step": "awaiting_new_amount",
        "split_type": "personal",
        "raw_merchant": "Starbucks",
        "overflow_categories": [],
    })

    redis = _make_redis(stored)

    mock_txn = MagicMock()
    mock_txn.id = txn_id
    mock_txn.raw_merchant_name = "Starbucks"
    mock_txn.amount = 5000
    mock_txn.currency = "CLP"
    mock_txn.bank_account_id = None

    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none = MagicMock(return_value=mock_txn)
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_execute_result)

    with patch("modules.whatsapp.handler.send_expense_alert", new_callable=AsyncMock, return_value="wamid.NEW2"), \
         patch("modules.whatsapp.handler.get_user_ranked_categories", new_callable=AsyncMock, return_value=[]):
        await handle_text_message(phone=phone, text="12500", db=mock_db, redis=redis)

    assert mock_txn.amount == 12500
    assert f"wa_active_edit:{phone}" not in stored


@pytest.mark.asyncio
async def test_handle_text_message_invalid_amount_sends_error():
    """Non-numeric amount reply sends error text and returns without DB update."""
    stored = {}
    phone = "56912345678"
    txn_id = "txn-err"

    stored[f"wa_active_edit:{phone}"] = txn_id
    stored[_session_key(phone, txn_id)] = json.dumps({
        "transaction_id": txn_id,
        "step": "awaiting_new_amount",
        "split_type": "",
        "raw_merchant": "Copec",
        "overflow_categories": [],
    })

    redis = _make_redis(stored)
    mock_db = AsyncMock()

    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none = MagicMock(return_value=MagicMock(
        id=txn_id,
        raw_merchant_name="Copec",
        amount=48000,
        currency="CLP",
        bank_account_id=None,
    ))
    mock_db.execute = AsyncMock(return_value=mock_execute_result)

    with patch("modules.whatsapp.handler.send_text", new_callable=AsyncMock, return_value="wamid.ERR") as mock_send:
        await handle_text_message(phone=phone, text="not a number", db=mock_db, redis=redis)

    mock_send.assert_called_once()
    body_arg = mock_send.call_args.kwargs.get("body") or (mock_send.call_args.args[1] if len(mock_send.call_args.args) > 1 else "")
    assert "número" in body_arg.lower() or "numero" in body_arg.lower()
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_handle_text_message_no_active_edit_ignores():
    """If no active_edit key exists and message is unparseable, handler silently returns."""
    stored = {}
    redis = _make_redis(stored)
    mock_db = AsyncMock()

    await handle_text_message(phone="56900000000", text="hello", db=mock_db, redis=redis)
    mock_db.execute.assert_not_called()


# ---------------------------------------------------------------------------
# parse_manual_expense — unit tests
# ---------------------------------------------------------------------------

def test_parse_manual_expense_with_gasto_keyword():
    assert parse_manual_expense("gasto 5000 Starbucks") == (5000, "Starbucks")


def test_parse_manual_expense_without_keyword():
    assert parse_manual_expense("5000 Starbucks") == (5000, "Starbucks")


def test_parse_manual_expense_dot_thousands_separator():
    assert parse_manual_expense("gasto 15.990 Copec") == (15990, "Copec")


def test_parse_manual_expense_multi_word_merchant():
    assert parse_manual_expense("gasto 3500 Café del Centro") == (3500, "Café del Centro")


def test_parse_manual_expense_no_merchant_returns_none():
    assert parse_manual_expense("5000") is None


def test_parse_manual_expense_no_amount_returns_none():
    assert parse_manual_expense("gasto Starbucks") is None


def test_parse_manual_expense_empty_returns_none():
    assert parse_manual_expense("") is None


def test_parse_manual_expense_whole_number_no_decimal():
    assert parse_manual_expense("gasto 25 Taxi") == (25, "Taxi")


def test_parse_manual_expense_decimal_two_places():
    # 25.00 → 25.0 (USD whole dollars written with cents)
    assert parse_manual_expense("gasto 25.00 Starbucks") == (25.0, "Starbucks")


def test_parse_manual_expense_decimal_one_place():
    # 2.5 → 2.5 (USD fractional)
    assert parse_manual_expense("gasto 2.5 Coffee") == (2.5, "Coffee")


def test_parse_manual_expense_dot_three_digits_is_thousands():
    # 15.990 → 15990 (CLP thousands separator)
    assert parse_manual_expense("gasto 15.990 Copec") == (15990, "Copec")


def test_parse_manual_expense_comma_thousands_separator():
    # 1,500 → 1500
    assert parse_manual_expense("gasto 1,500 Supermercado") == (1500, "Supermercado")


# ---------------------------------------------------------------------------
# handle_text_message — manual expense trigger (no active edit)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_text_message_manual_trigger_creates_transaction():
    """Valid 'gasto N merchant' with no active edit creates a transaction and sends alert."""
    stored = {}
    phone = "56912345678"
    user_id = uuid.uuid4()
    household_id = uuid.uuid4()

    redis = _make_redis(stored)

    mock_row = (user_id, household_id, "USD")
    mock_execute_result = MagicMock()
    mock_execute_result.first = MagicMock(return_value=mock_row)
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_execute_result)
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    with patch("modules.whatsapp.handler.send_expense_alert", new_callable=AsyncMock, return_value="wamid.MANUAL") as mock_alert, \
         patch("modules.whatsapp.handler.get_user_ranked_categories", new_callable=AsyncMock, return_value=["Restaurantes", "Café"]):
        await handle_text_message(phone=phone, text="gasto 5000 Starbucks", db=mock_db, redis=redis)

    # Transaction must use user's preferred currency, not hardcoded CLP
    added_txn = mock_db.add.call_args[0][0]
    assert added_txn.status == "confirmed"
    assert added_txn.source == "manual"
    assert added_txn.currency == "USD"
    mock_db.commit.assert_called_once()
    mock_alert.assert_called_once()
    # Session must be saved in redis
    assert any("wa_session" in key for key in stored)
    # Message ID must be mapped to the new transaction
    assert "wa_msgid:wamid.MANUAL" in stored


@pytest.mark.asyncio
async def test_handle_text_message_manual_trigger_unknown_phone_ignores():
    """Valid trigger but phone not found in DB — silently returns without creating anything."""
    stored = {}
    phone = "56999999999"

    redis = _make_redis(stored)

    mock_execute_result = MagicMock()
    mock_execute_result.first = MagicMock(return_value=None)  # no user found
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_execute_result)
    mock_db.add = MagicMock()

    with patch("modules.whatsapp.handler.send_expense_alert", new_callable=AsyncMock) as mock_alert:
        await handle_text_message(phone=phone, text="gasto 5000 Starbucks", db=mock_db, redis=redis)

    mock_db.add.assert_not_called()
    mock_alert.assert_not_called()
