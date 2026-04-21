# backend/tests/test_delete_transaction.py
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_delete_pending_email_transaction():
    """Can delete a pending email transaction."""
    from modules.transactions.service import delete_transaction

    user_id = uuid.uuid4()
    txn_id = uuid.uuid4()

    mock_txn = MagicMock()
    mock_txn.id = txn_id
    mock_txn.user_id = user_id
    mock_txn.source = "gmail"
    mock_txn.source_type = "email"
    mock_txn.status = "pending"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_txn

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    result = await delete_transaction(mock_db, txn_id, user_id)
    assert result == "deleted"
    mock_db.delete.assert_called_once_with(mock_txn)


@pytest.mark.asyncio
async def test_delete_orphan_email_transaction():
    """Can delete an orphaned email transaction (aged out by reconciliation tick)."""
    from modules.transactions.service import delete_transaction

    user_id = uuid.uuid4()
    txn_id = uuid.uuid4()

    mock_txn = MagicMock()
    mock_txn.id = txn_id
    mock_txn.user_id = user_id
    mock_txn.source = "outlook"
    mock_txn.source_type = "email"
    mock_txn.status = "orphan"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_txn

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    result = await delete_transaction(mock_db, txn_id, user_id)
    assert result == "deleted"
    mock_db.delete.assert_called_once_with(mock_txn)


@pytest.mark.asyncio
async def test_delete_rejects_connect_transaction():
    """Cannot delete a connect-sourced (scraped) transaction."""
    from modules.transactions.service import delete_transaction

    user_id = uuid.uuid4()
    txn_id = uuid.uuid4()

    mock_txn = MagicMock()
    mock_txn.id = txn_id
    mock_txn.user_id = user_id
    mock_txn.source = "connect"
    mock_txn.source_type = "connect"
    mock_txn.status = "settled"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_txn

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await delete_transaction(mock_db, txn_id, user_id)
    assert result == "invalid"


@pytest.mark.asyncio
async def test_delete_rejects_settled_email_transaction():
    """Cannot delete a settled email transaction — only pending or orphan."""
    from modules.transactions.service import delete_transaction

    user_id = uuid.uuid4()
    txn_id = uuid.uuid4()

    mock_txn = MagicMock()
    mock_txn.id = txn_id
    mock_txn.user_id = user_id
    mock_txn.source = "gmail"
    mock_txn.source_type = "email"
    mock_txn.status = "settled"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_txn

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await delete_transaction(mock_db, txn_id, user_id)
    assert result == "invalid"


@pytest.mark.asyncio
async def test_delete_returns_not_found():
    """Transaction not found returns not_found."""
    from modules.transactions.service import delete_transaction

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await delete_transaction(mock_db, uuid.uuid4(), uuid.uuid4())
    assert result == "not_found"
