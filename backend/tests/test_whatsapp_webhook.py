import pytest
from unittest.mock import AsyncMock
from modules.whatsapp.session import (
    WhatsAppSession,
    save_session,
    get_session,
    clear_session,
    save_msgid,
    get_transaction_id_by_msgid,
    save_active_edit,
    get_active_edit_transaction_id,
    clear_active_edit,
)


@pytest.mark.asyncio
async def test_save_and_retrieve_session():
    stored = {}
    mock_redis = AsyncMock()

    async def mock_setex(key, ttl, val):
        stored[key] = val

    async def mock_get(key):
        return stored.get(key)

    mock_redis.setex = mock_setex
    mock_redis.get = mock_get

    session = WhatsAppSession(transaction_id="txn-123", step="awaiting_split")
    await save_session("+56912345678", session, mock_redis)

    # Key must include transaction_id
    assert "wa_session:56912345678:txn-123" in stored

    retrieved = await get_session("+56912345678", "txn-123", mock_redis)
    assert retrieved.transaction_id == "txn-123"
    assert retrieved.step == "awaiting_split"


@pytest.mark.asyncio
async def test_get_session_returns_none_when_missing():
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    result = await get_session("+56999999999", "txn-999", mock_redis)
    assert result is None


@pytest.mark.asyncio
async def test_clear_session_deletes_correct_key():
    deleted = []
    mock_redis = AsyncMock()
    mock_redis.delete = AsyncMock(side_effect=lambda *keys: deleted.extend(keys))

    await clear_session("+56912345678", "txn-123", mock_redis)
    assert deleted == ["wa_session:56912345678:txn-123"]


@pytest.mark.asyncio
async def test_save_and_retrieve_msgid():
    stored = {}
    mock_redis = AsyncMock()

    async def mock_setex(key, ttl, val):
        stored[key] = (ttl, val)

    async def mock_get(key):
        entry = stored.get(key)
        return entry[1] if isinstance(entry, tuple) else entry

    mock_redis.setex = mock_setex
    mock_redis.get = mock_get

    await save_msgid("wamid.ABC123", "txn-123", mock_redis)
    assert "wa_msgid:wamid.ABC123" in stored
    assert stored["wa_msgid:wamid.ABC123"][0] == 86400  # _SESSION_TTL

    result = await get_transaction_id_by_msgid("wamid.ABC123", mock_redis)
    assert result == "txn-123"


@pytest.mark.asyncio
async def test_get_msgid_returns_none_when_missing():
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    result = await get_transaction_id_by_msgid("wamid.UNKNOWN", mock_redis)
    assert result is None


@pytest.mark.asyncio
async def test_save_and_retrieve_active_edit():
    stored = {}
    mock_redis = AsyncMock()

    async def mock_setex(key, ttl, val):
        stored[key] = val

    async def mock_get(key):
        return stored.get(key)

    mock_redis.setex = mock_setex
    mock_redis.get = mock_get

    await save_active_edit("+56912345678", "txn-abc", mock_redis)
    assert stored["wa_active_edit:56912345678"] == "txn-abc"

    result = await get_active_edit_transaction_id("+56912345678", mock_redis)
    assert result == "txn-abc"


@pytest.mark.asyncio
async def test_get_active_edit_returns_none_when_missing():
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    result = await get_active_edit_transaction_id("+56999999999", mock_redis)
    assert result is None


@pytest.mark.asyncio
async def test_clear_active_edit_deletes_correct_key():
    deleted = []
    mock_redis = AsyncMock()
    mock_redis.delete = AsyncMock(side_effect=lambda *keys: deleted.extend(keys))

    await clear_active_edit("+56912345678", mock_redis)
    assert deleted == ["wa_active_edit:56912345678"]
