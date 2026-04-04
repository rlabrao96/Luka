import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from modules.whatsapp.handler import handle_text_message
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
         patch("modules.whatsapp.handler.lookup_merchant", new_callable=AsyncMock, return_value=["Restaurantes"]):
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
         patch("modules.whatsapp.handler.lookup_merchant", new_callable=AsyncMock, return_value=[]):
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
    """If no active_edit key exists, handler silently returns."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_db = AsyncMock()

    await handle_text_message(phone="56900000000", text="hello", db=mock_db, redis=mock_redis)
    mock_db.execute.assert_not_called()
