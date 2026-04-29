"""Tests for scripts/backfill_pending_consolidation.py.

Real DB via the savepoint `db` fixture. We invoke `_backfill_household` with
`commit_per_pair=False` so the suite-wide rollback still works.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

# Register every model so Base.metadata resolves cross-table FKs.
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.transactions.models import Transaction, TransactionSplit
from scripts.backfill_pending_consolidation import _backfill_household


# ---------------------------------------------------------------- helpers


async def _seed_household(
    db,
    *,
    bank_name: str = "BCP",
    account_type: str = "personal",
    currency: str = "USD",
) -> tuple[User, Household, BankAccount]:
    user = User(
        id=uuid.uuid4(),
        email=f"bf-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="Backfill Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency=currency,
    )
    db.add(user)
    await db.flush()

    household = Household(id=uuid.uuid4(), name="HH", type="individual")
    db.add(household)
    await db.flush()

    db.add(HouseholdMember(household_id=household.id, user_id=user.id, role="owner"))
    await db.flush()

    account = BankAccount(
        id=uuid.uuid4(),
        household_id=household.id,
        user_id=user.id,
        bank_name=bank_name,
        account_type=account_type,
        currency=currency,
        is_active=True,
    )
    db.add(account)
    await db.flush()
    return user, household, account


def _email(
    *,
    user: User,
    household: Household,
    account: BankAccount | None,
    amount: Decimal,
    when: datetime,
    merchant: str = "Amazon",
    currency: str = "USD",
    tx_type: str = "expense",
    source_bank_name: str | None = None,
) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=household.id,
        bank_account_id=account.id if account else None,
        raw_merchant_name=merchant,
        amount=amount,
        currency=currency,
        transaction_date=when,
        source="gmail",
        source_type="email",
        status="pending",
        transaction_type=tx_type,
        source_bank_name=source_bank_name,
    )


def _plaid_pending(
    *,
    user: User,
    household: Household,
    account: BankAccount,
    amount: Decimal,
    when: datetime,
    merchant: str = "Amazon",
    currency: str = "USD",
    tx_type: str = "expense",
) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=household.id,
        bank_account_id=account.id,
        raw_merchant_name=merchant,
        amount=amount,
        currency=currency,
        transaction_date=when,
        source="plaid",
        source_type="plaid",
        status="pending",
        transaction_type=tx_type,
    )


async def _exists(db, tx_id: uuid.UUID) -> bool:
    res = await db.execute(select(Transaction.id).where(Transaction.id == tx_id))
    return res.scalar_one_or_none() is not None


# ---------------------------------------------------------------- tests


@pytest.mark.asyncio
async def test_consolidates_one_email_one_plaid(db):
    user, hh, acc = await _seed_household(db)
    when = datetime.now(timezone.utc) - timedelta(days=1)

    e = _email(user=user, household=hh, account=None, amount=Decimal("-27.43"), when=when)
    p = _plaid_pending(user=user, household=hh, account=acc, amount=Decimal("-27.43"), when=when)
    db.add_all([e, p])
    await db.flush()

    r = await _backfill_household(db, hh.id, dry_run=False, limit=None, commit_per_pair=False)
    assert r["merged"] == 1
    assert r["ambiguous"] == 0

    assert await _exists(db, e.id) is False
    assert await _exists(db, p.id) is True


@pytest.mark.asyncio
async def test_no_change_when_only_email_pending(db):
    user, hh, acc = await _seed_household(db)
    when = datetime.now(timezone.utc) - timedelta(days=1)

    e = _email(user=user, household=hh, account=None, amount=Decimal("-50.00"), when=when)
    db.add(e)
    await db.flush()

    r = await _backfill_household(db, hh.id, dry_run=False, limit=None, commit_per_pair=False)
    assert r["merged"] == 0
    assert r["ambiguous"] == 0
    assert await _exists(db, e.id) is True


@pytest.mark.asyncio
async def test_idempotent_second_run_is_noop(db):
    user, hh, acc = await _seed_household(db)
    when = datetime.now(timezone.utc) - timedelta(days=1)

    e = _email(user=user, household=hh, account=None, amount=Decimal("-12.00"), when=when)
    p = _plaid_pending(user=user, household=hh, account=acc, amount=Decimal("-12.00"), when=when)
    db.add_all([e, p])
    await db.flush()

    r1 = await _backfill_household(db, hh.id, dry_run=False, limit=None, commit_per_pair=False)
    assert r1["merged"] == 1

    r2 = await _backfill_household(db, hh.id, dry_run=False, limit=None, commit_per_pair=False)
    assert r2["merged"] == 0
    assert r2["ambiguous"] == 0


@pytest.mark.asyncio
async def test_ambiguous_two_plaid_candidates_skips(db):
    user, hh, acc = await _seed_household(db)
    when = datetime.now(timezone.utc) - timedelta(days=1)

    e = _email(user=user, household=hh, account=None, amount=Decimal("-9.99"), when=when)
    p1 = _plaid_pending(user=user, household=hh, account=acc, amount=Decimal("-9.99"), when=when)
    p2 = _plaid_pending(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("-9.99"),
        when=when + timedelta(hours=2),
    )
    db.add_all([e, p1, p2])
    await db.flush()

    r = await _backfill_household(db, hh.id, dry_run=False, limit=None, commit_per_pair=False)
    assert r["merged"] == 0
    assert r["ambiguous"] == 1
    assert await _exists(db, e.id) is True
    assert await _exists(db, p1.id) is True
    assert await _exists(db, p2.id) is True


@pytest.mark.asyncio
async def test_joint_account_forces_shared_split(db):
    user, hh, acc = await _seed_household(db, account_type="joint")
    when = datetime.now(timezone.utc) - timedelta(days=1)

    e = _email(user=user, household=hh, account=None, amount=Decimal("-77.00"), when=when)
    p = _plaid_pending(user=user, household=hh, account=acc, amount=Decimal("-77.00"), when=when)
    db.add_all([e, p])
    await db.flush()

    # Email side has a 'personal' split — backfill must override to 'shared'
    db.add(
        TransactionSplit(
            id=uuid.uuid4(),
            transaction_id=e.id,
            split_type="personal",
        )
    )
    await db.flush()

    r = await _backfill_household(db, hh.id, dry_run=False, limit=None, commit_per_pair=False)
    assert r["merged"] == 1

    split_row = await db.execute(
        select(TransactionSplit.split_type).where(TransactionSplit.transaction_id == p.id)
    )
    assert split_row.scalar_one() == "shared"


@pytest.mark.asyncio
async def test_cross_bank_guard_blocks_merge(db):
    # Plaid lives at BBVA, email says source_bank_name=BCP — must not merge.
    user, hh, acc = await _seed_household(db, bank_name="BBVA")
    when = datetime.now(timezone.utc) - timedelta(days=1)

    e = _email(
        user=user,
        household=hh,
        account=None,
        amount=Decimal("-33.00"),
        when=when,
        source_bank_name="BCP",
    )
    p = _plaid_pending(user=user, household=hh, account=acc, amount=Decimal("-33.00"), when=when)
    db.add_all([e, p])
    await db.flush()

    r = await _backfill_household(db, hh.id, dry_run=False, limit=None, commit_per_pair=False)
    assert r["merged"] == 0
    assert r["ambiguous"] == 0
    assert await _exists(db, e.id) is True
    assert await _exists(db, p.id) is True


@pytest.mark.asyncio
async def test_two_households_only_first_has_pair(db):
    # H1: pair → merges. H2: email-only → no change.
    u1, h1, a1 = await _seed_household(db)
    u2, h2, a2 = await _seed_household(db)
    when = datetime.now(timezone.utc) - timedelta(days=1)

    e1 = _email(user=u1, household=h1, account=None, amount=Decimal("-10.00"), when=when)
    p1 = _plaid_pending(user=u1, household=h1, account=a1, amount=Decimal("-10.00"), when=when)
    e2 = _email(user=u2, household=h2, account=None, amount=Decimal("-20.00"), when=when)
    db.add_all([e1, p1, e2])
    await db.flush()

    r1 = await _backfill_household(db, h1.id, dry_run=False, limit=None, commit_per_pair=False)
    r2 = await _backfill_household(db, h2.id, dry_run=False, limit=None, commit_per_pair=False)

    assert r1["merged"] == 1
    assert r2["merged"] == 0
    assert await _exists(db, e1.id) is False
    assert await _exists(db, p1.id) is True
    assert await _exists(db, e2.id) is True
