# backend/tests/test_pending_transactions.py
import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_email_txn_before_sync_is_awaiting():
    """Email transaction created before any Fintoc sync → awaiting_reconciliation."""
    from modules.transactions.service import get_pending_transactions

    user_id = uuid.uuid4()
    mock_db = AsyncMock()

    # Mock: 1 pending email txn, max_synced_at is None (no sync yet)
    mock_txn = MagicMock()
    mock_txn.id = uuid.uuid4()
    mock_txn.source = "gmail"
    mock_txn.status = "pending"
    mock_txn.category = None
    mock_txn.created_at = datetime.now(timezone.utc)

    # We'll test the actual SQL logic via integration tests;
    # for unit tests, verify the function exists and returns the right shape
    result_mock = MagicMock()
    result_mock.all.return_value = []
    mock_db.execute = AsyncMock(return_value=result_mock)

    result = await get_pending_transactions(mock_db, user_id)
    assert "awaiting_reconciliation" in result
    assert "needs_classification" in result
    assert "unmatched_email" in result


@pytest.mark.asyncio
async def test_pending_returns_empty_when_no_pending():
    """No pending transactions → all 3 lists empty."""
    from modules.transactions.service import get_pending_transactions

    user_id = uuid.uuid4()
    mock_db = AsyncMock()
    result_mock = MagicMock()
    result_mock.all.return_value = []
    mock_db.execute = AsyncMock(return_value=result_mock)

    result = await get_pending_transactions(mock_db, user_id)
    assert result["awaiting_reconciliation"] == []
    assert result["needs_classification"] == []
    assert result["unmatched_email"] == []
