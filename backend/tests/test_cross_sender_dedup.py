# backend/tests/test_cross_sender_dedup.py
import pytest
from modules.transactions.service import is_duplicate_transaction
from unittest.mock import AsyncMock, MagicMock
import uuid


@pytest.mark.asyncio
async def test_detects_duplicate_within_5_minutes():
    """Same amount + within 5 minutes of created_at → duplicate."""
    user_id = uuid.uuid4()
    mock_existing = MagicMock()
    mock_existing.id = uuid.uuid4()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_existing

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await is_duplicate_transaction(mock_db, user_id, 25990)
    assert result is True


@pytest.mark.asyncio
async def test_no_duplicate_when_none_found():
    """No matching transaction → not a duplicate."""
    user_id = uuid.uuid4()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await is_duplicate_transaction(mock_db, user_id, 25990)
    assert result is False
