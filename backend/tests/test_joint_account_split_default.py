"""Pin down the joint-account split-type default at the Plaid sync and
bank_connect ingestion entry points.

Bug: ``ensure_default_split(db, txn)`` accepts a ``default_split_type`` kwarg
(default ``"personal"``). The email path passes ``"shared"`` for joint
accounts. The Plaid path (``modules/plaid/sync.py``) and bank_connect path
(``modules/bank_connect/router.py``) call it WITHOUT the kwarg — so a
transaction landing on a joint account gets split_type='personal' instead of
'shared'.

These tests reproduce the bug at the smallest unit of behaviour around each
call site. They are expected to FAIL on the current `main` and PASS once
Task 2 plumbs the correct default through.

Uses the savepoint-rollback ``db`` fixture from conftest.py. Real database, no
DB mocks (per CLAUDE.md).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

# Register every model so Base.metadata resolves each FK on flush.
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.bank_connect.models import BankCredential
from modules.bank_connect.router import _process_movements
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.transactions.models import Transaction, TransactionSplit


# ---------------------------------------------------------------- helpers


async def _seed_household(db, account_type: str) -> tuple[User, Household, BankAccount]:
    """Create a user + household + bank account of the given type, all flushed."""
    user = User(
        id=uuid.uuid4(),
        email=f"{account_type}-{uuid.uuid4().hex[:8]}@luka.test",
        full_name=f"{account_type.title()} Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency="CLP",
    )
    db.add(user)
    await db.flush()

    household = Household(id=uuid.uuid4(), name=f"{account_type.title()} HH", type="couple")
    db.add(household)
    await db.flush()

    db.add(HouseholdMember(household_id=household.id, user_id=user.id, role="owner"))
    await db.flush()

    account = BankAccount(
        id=uuid.uuid4(),
        household_id=household.id,
        user_id=user.id,
        bank_name="Bank Of America",
        account_type=account_type,  # <-- the case under test
        account_kind="checking_account",
        account_name=f"{account_type.title()} Checking",
        currency="CLP",
        is_active=True,
    )
    db.add(account)
    await db.flush()
    return user, household, account


async def _seed_joint_household(db) -> tuple[User, Household, BankAccount]:
    """Create a user + household + JOINT bank account, all flushed."""
    return await _seed_household(db, "joint")


# ---------------------------------------------------------------- Plaid path


async def test_plaid_sync_joint_account_defaults_split_to_shared(db):
    """Replicate the Plaid sync call site:

        new_tx = Transaction(**tx_data)
        session.add(new_tx); await session.flush()
        await ensure_default_split(session, new_tx)

    A txn landing on a joint account MUST end up with split_type='shared'.
    Currently fails — the call site forgets to pass default_split_type.
    """
    from modules.transactions.service import ensure_default_split

    user, household, account = await _seed_joint_household(db)

    new_tx = Transaction(
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
        transaction_type="expense",
    )
    db.add(new_tx)
    await db.flush()

    # This is the literal call from modules/plaid/sync.py:225-231.
    await ensure_default_split(db, new_tx)
    await db.flush()

    split = (
        await db.execute(
            select(TransactionSplit).where(TransactionSplit.transaction_id == new_tx.id)
        )
    ).scalar_one_or_none()

    assert split is not None, "Plaid path must create a default split row"
    assert split.split_type == "shared", (
        f"Joint account Plaid txn defaulted to {split.split_type!r}; expected 'shared'."
    )


# ---------------------------------------------------------------- bank_connect path


async def test_bank_connect_process_movements_joint_account_defaults_to_shared(db):
    """Invoke `_process_movements` directly on a joint account.

    The function maps the movement → Transaction, flushes, and calls
    ``ensure_default_split(db, txn)`` (no kwarg). The resulting split row
    MUST be 'shared' for a joint account.
    """
    user, household, account = await _seed_joint_household(db)

    # Minimal BankCredential just so _process_movements can read user_id.
    cred = BankCredential(
        id=uuid.uuid4(),
        user_id=user.id,
        bank_code="bci",
        encrypted_rut=b"x",
        encrypted_password=b"x",
        encryption_iv=b"x",
    )
    db.add(cred)
    await db.flush()

    # Movement shaped to land in the seeded joint BankAccount via ba_map lookup.
    # `account.account_name` is the lookup key paired with currency.
    movement = {
        "accountName": account.account_name,
        "currency": "CLP",
        "source": "checking_account",
        "amount": -5000,
        "description": "STARBUCKS NUMERO 9",
        "date": "2025-01-15",
        "time": "12:30",
    }
    ba_map = {(account.account_name, "CLP"): account.id}

    created, enriched, skipped = await _process_movements(db, cred, [movement], ba_map)
    assert created == 1, (
        f"expected 1 created, got created={created} enriched={enriched} skipped={skipped}"
    )
    await db.flush()

    # Find the inserted txn (only one connect txn for this user in this test).
    txn = (
        await db.execute(
            select(Transaction).where(
                Transaction.user_id == user.id,
                Transaction.source == "connect",
            )
        )
    ).scalar_one()

    split = (
        await db.execute(select(TransactionSplit).where(TransactionSplit.transaction_id == txn.id))
    ).scalar_one_or_none()

    assert split is not None, "bank_connect path must create a default split row"
    assert split.split_type == "shared", (
        f"Joint account bank_connect txn defaulted to {split.split_type!r}; expected 'shared'."
    )


# ---------------------------------------------------------------- partner path


async def test_partner_account_defaults_split_to_partner(db):
    """An additional / authorized-user card marked account_type='partner'
    (the partner's own card) must default its new transactions to
    split_type='partner' so they never count as the owner's spending."""
    from modules.transactions.service import ensure_default_split

    user, household, account = await _seed_household(db, "partner")

    new_tx = Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=household.id,
        bank_account_id=account.id,
        raw_merchant_name="Sephora",
        amount=Decimal("-40000"),
        currency="CLP",
        transaction_date=datetime.now(timezone.utc),
        source="plaid",
        source_type="plaid",
        status="settled",
        transaction_type="expense",
    )
    db.add(new_tx)
    await db.flush()

    await ensure_default_split(db, new_tx, default_split_type=_split_default_for("partner"))
    await db.flush()

    split = (
        await db.execute(
            select(TransactionSplit).where(TransactionSplit.transaction_id == new_tx.id)
        )
    ).scalar_one_or_none()

    assert split is not None, "partner account must create a default split row"
    assert split.split_type == "partner", (
        f"Partner account txn defaulted to {split.split_type!r}; expected 'partner'."
    )


async def test_partner_spending_excluded_from_dashboard_summary(db):
    """The owner's dashboard summary must exclude a partner-account expense —
    her spending is not his money."""
    from modules.transactions.service import ensure_default_split, get_dashboard_summary

    user, household, account = await _seed_household(db, "partner")

    txn = Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=household.id,
        bank_account_id=account.id,
        raw_merchant_name="Sephora",
        amount=Decimal("-40000"),
        currency="CLP",
        transaction_date=datetime.now(timezone.utc),
        source="plaid",
        source_type="plaid",
        status="settled",
        transaction_type="expense",
    )
    db.add(txn)
    await db.flush()
    await ensure_default_split(db, txn, default_split_type=_split_default_for("partner"))
    await db.flush()

    month = datetime.now(timezone.utc).strftime("%Y-%m")
    summary = await get_dashboard_summary(db, user.id, month, "CLP")

    assert summary["expenses"] == 0, (
        f"partner-account expense leaked into owner's dashboard (expenses={summary['expenses']})"
    )
    assert summary["categories"] == [], (
        "partner-account expense leaked into owner's category breakdown"
    )


def _split_default_for(account_type: str) -> str:
    from modules.transactions.service import split_type_for_account

    return split_type_for_account(account_type)
