import pytest
from unittest.mock import AsyncMock
from modules.whatsapp.session import WhatsAppSession, save_session, get_session


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
    retrieved = await get_session("+56912345678", mock_redis)
    assert retrieved.transaction_id == "txn-123"
    assert retrieved.step == "awaiting_split"


@pytest.mark.asyncio
async def test_get_session_returns_none_when_missing():
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    result = await get_session("+56999999999", mock_redis)
    assert result is None
