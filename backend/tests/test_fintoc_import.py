import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from modules.fintoc.client import FintocTransaction
from modules.transactions.models import TransactionSplit


def make_fintoc_txn(id: str, amount: int = -10000, description: str = "LIDER") -> FintocTransaction:
    return FintocTransaction(
        id=id,
        amount=amount,
        description=description,
        transaction_date=datetime(2026, 1, 15, tzinfo=timezone.utc),
        account_id="acc_test",
    )


def make_mock_account(account_type: str = "personal"):
    account = MagicMock()
    account.id = "ba_1"
    account.fintoc_link_id = "lt_test"
    account.fintoc_account_id = "acc_test"
    account.account_type = account_type
    account.user_id = "user_1"
    account.household_id = "hh_1"
    return account


@pytest.mark.asyncio
async def test_import_creates_transactions_and_splits():
    """Happy path: two Fintoc transactions → two Transaction + two TransactionSplit rows."""
    from jobs.tasks import import_fintoc_history

    mock_account = make_mock_account("personal")
    added_objects = []

    with (
        patch("jobs.tasks.AsyncSessionLocal") as MockSession,
        patch("jobs.tasks.FintocClient") as MockClient,
    ):
        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_account)
        mock_db.scalar = AsyncMock(return_value=None)  # no existing fintoc_id
        mock_db.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        MockSession.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        MockSession.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_client = AsyncMock()
        mock_client.fetch_transactions = AsyncMock(
            return_value=[
                make_fintoc_txn("ft_1"),
                make_fintoc_txn("ft_2", description="UBER"),
            ]
        )
        MockClient.return_value = mock_client

        await import_fintoc_history({}, bank_account_id="ba_1")

    from modules.transactions.models import Transaction

    transactions = [o for o in added_objects if isinstance(o, Transaction)]
    splits = [o for o in added_objects if isinstance(o, TransactionSplit)]
    assert len(transactions) == 2
    assert len(splits) == 2
    assert mock_account.import_status == "done"


@pytest.mark.asyncio
async def test_import_skips_existing_fintoc_id():
    """Idempotency: if fintoc_id already in DB, skip without creating duplicate."""
    from jobs.tasks import import_fintoc_history

    mock_account = make_mock_account()

    with (
        patch("jobs.tasks.AsyncSessionLocal") as MockSession,
        patch("jobs.tasks.FintocClient") as MockClient,
    ):
        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_account)
        mock_db.scalar = AsyncMock(return_value=MagicMock())  # existing txn found
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        MockSession.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        MockSession.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_client = AsyncMock()
        mock_client.fetch_transactions = AsyncMock(return_value=[make_fintoc_txn("ft_exists")])
        MockClient.return_value = mock_client

        await import_fintoc_history({}, bank_account_id="ba_1")

    mock_db.add.assert_not_called()
    assert mock_account.import_status == "done"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "account_type,expected_split",
    [
        ("personal", "personal"),
        ("partner", "partner"),
        ("joint", "shared"),
    ],
)
async def test_import_split_type_mapping(account_type, expected_split):
    """Account label correctly maps to TransactionSplit.split_type."""
    from jobs.tasks import import_fintoc_history

    mock_account = make_mock_account(account_type)
    added_objects = []

    with (
        patch("jobs.tasks.AsyncSessionLocal") as MockSession,
        patch("jobs.tasks.FintocClient") as MockClient,
    ):
        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_account)
        mock_db.scalar = AsyncMock(return_value=None)
        mock_db.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        MockSession.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        MockSession.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_client = AsyncMock()
        mock_client.fetch_transactions = AsyncMock(return_value=[make_fintoc_txn("ft_1")])
        MockClient.return_value = mock_client

        await import_fintoc_history({}, bank_account_id="ba_1")

    splits = [o for o in added_objects if isinstance(o, TransactionSplit)]
    assert len(splits) == 1
    assert splits[0].split_type == expected_split


@pytest.mark.asyncio
async def test_import_sets_status_failed_on_error():
    """On Fintoc API error, import_status is set to 'failed' and job is logged."""
    from jobs.tasks import import_fintoc_history

    mock_account = make_mock_account()
    mock_failed_account = MagicMock()

    mock_main_db = AsyncMock()
    mock_main_db.get = AsyncMock(return_value=mock_account)
    mock_main_db.add = MagicMock()
    mock_main_db.commit = AsyncMock()
    mock_main_db.refresh = AsyncMock()

    mock_fresh_db = AsyncMock()
    mock_fresh_db.get = AsyncMock(return_value=mock_failed_account)
    mock_fresh_db.add = MagicMock()
    mock_fresh_db.commit = AsyncMock()

    call_count = 0

    def make_session_cm():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(return_value=mock_main_db)
            cm.__aexit__ = AsyncMock(return_value=None)
        else:
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(return_value=mock_fresh_db)
            cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with (
        patch("jobs.tasks.AsyncSessionLocal", side_effect=make_session_cm),
        patch("jobs.tasks.FintocClient") as MockClient,
    ):
        mock_client = AsyncMock()
        mock_client.fetch_transactions = AsyncMock(side_effect=Exception("Fintoc API down"))
        MockClient.return_value = mock_client

        await import_fintoc_history({}, bank_account_id="ba_1")

    assert mock_failed_account.import_status == "failed"
    from modules.transactions.models import FailedJob

    failed_jobs = [o for o in mock_fresh_db.add.call_args_list if isinstance(o.args[0], FailedJob)]
    assert len(failed_jobs) == 1
