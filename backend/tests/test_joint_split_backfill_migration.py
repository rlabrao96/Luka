"""Test the historical backfill SQL from migration 1d4edef10702.

Seeds a household with both a joint and a personal bank account, plants
``split_type='personal'`` rows on each, runs the migration's UPDATE
verbatim, and asserts the joint-account row flips to 'shared' while the
personal-account row is left alone. Also seeds a transfer with a stray
split row to pin down the transaction_type filter.

Uses the savepoint-rollback ``db`` fixture from conftest.py — real
database, no DB mocks (per CLAUDE.md).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import text

# Register every model so Base.metadata resolves each FK on flush.
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.transactions.models import Transaction, TransactionSplit


# Migration UPDATE under test — keep verbatim with the migration body.
BACKFILL_SQL = """
    UPDATE transaction_splits ts
    SET split_type = 'shared'
    FROM transactions t
    JOIN bank_accounts ba ON ba.id = t.bank_account_id
    WHERE ts.transaction_id = t.id
      AND ba.account_type = 'joint'
      AND ts.split_type = 'personal'
      AND t.transaction_type != 'transfer'
"""


async def _seed_user_and_household(db) -> tuple[User, Household]:
    user = User(
        id=uuid.uuid4(),
        email=f"backfill-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="Backfill Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency="CLP",
    )
    db.add(user)
    await db.flush()

    household = Household(id=uuid.uuid4(), name="Backfill HH", type="couple")
    db.add(household)
    await db.flush()

    db.add(HouseholdMember(household_id=household.id, user_id=user.id, role="owner"))
    await db.flush()
    return user, household


async def _seed_account(db, user, household, *, account_type: str, name: str) -> BankAccount:
    account = BankAccount(
        id=uuid.uuid4(),
        household_id=household.id,
        user_id=user.id,
        bank_name="Test Bank",
        account_type=account_type,
        account_kind="checking_account",
        account_name=name,
        currency="CLP",
        is_active=True,
    )
    db.add(account)
    await db.flush()
    return account


async def _seed_txn_with_split(
    db,
    user,
    household,
    account,
    *,
    transaction_type: str,
    split_type: str,
) -> tuple[Transaction, TransactionSplit]:
    txn = Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=household.id,
        bank_account_id=account.id,
        raw_merchant_name="Starbucks",
        amount=Decimal("-12.50"),
        currency="CLP",
        transaction_date=datetime.now(timezone.utc),
        source="plaid",
        source_type="plaid",
        status="settled",
        transaction_type=transaction_type,
    )
    db.add(txn)
    await db.flush()

    split = TransactionSplit(
        id=uuid.uuid4(),
        transaction_id=txn.id,
        split_type=split_type,
    )
    db.add(split)
    await db.flush()
    return txn, split


async def test_backfill_corrects_joint_account_splits_only(db):
    """Plant three personal-typed splits across a joint expense, a personal
    expense, and a joint transfer (invariant). Run the backfill SQL and
    assert exactly the joint-expense row flips to 'shared'."""
    user, household = await _seed_user_and_household(db)

    joint_account = await _seed_account(
        db, user, household, account_type="joint", name="Joint Checking"
    )
    personal_account = await _seed_account(
        db, user, household, account_type="personal", name="My Checking"
    )

    _, joint_expense_split = await _seed_txn_with_split(
        db, user, household, joint_account, transaction_type="expense", split_type="personal"
    )
    _, personal_expense_split = await _seed_txn_with_split(
        db,
        user,
        household,
        personal_account,
        transaction_type="expense",
        split_type="personal",
    )
    # Stray split on a transfer (should not be possible per ensure_default_split,
    # but the migration filter is belt-and-suspenders; pin that down).
    _, joint_transfer_split = await _seed_txn_with_split(
        db, user, household, joint_account, transaction_type="transfer", split_type="personal"
    )

    # Run the migration's UPDATE within the savepoint.
    await db.execute(text(BACKFILL_SQL))
    await db.flush()

    # Re-fetch each split fresh from the database via raw SQL — bypasses the
    # identity-map cache so we see the post-UPDATE values.
    result = await db.execute(
        text("SELECT id, split_type FROM transaction_splits " "WHERE id = ANY(:ids)"),
        {
            "ids": [
                joint_expense_split.id,
                personal_expense_split.id,
                joint_transfer_split.id,
            ]
        },
    )
    by_id = {row.id: row.split_type for row in result}

    assert (
        by_id[joint_expense_split.id] == "shared"
    ), "Joint-account expense split should have been flipped to 'shared'."
    assert (
        by_id[personal_expense_split.id] == "personal"
    ), "Personal-account split must NOT be touched."
    assert (
        by_id[joint_transfer_split.id] == "personal"
    ), "Transfer-type txn split must NOT be touched (transaction_type filter)."


async def test_backfill_is_idempotent(db):
    """Running the backfill twice must yield the same result — already-corrected
    rows are skipped by the ``split_type = 'personal'`` filter."""
    user, household = await _seed_user_and_household(db)
    joint_account = await _seed_account(
        db, user, household, account_type="joint", name="Joint Checking"
    )
    _, split = await _seed_txn_with_split(
        db, user, household, joint_account, transaction_type="expense", split_type="personal"
    )

    await db.execute(text(BACKFILL_SQL))
    await db.execute(text(BACKFILL_SQL))
    await db.flush()

    result = await db.execute(
        text("SELECT split_type FROM transaction_splits WHERE id = :id"),
        {"id": split.id},
    )
    assert result.scalar_one() == "shared"
