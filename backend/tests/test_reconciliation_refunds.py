"""Tests for same-account refund/reversal pair detection.

Exercises detect_refunds against the live dev DB via the `db` savepoint fixture.
All inserts happen inside a nested SAVEPOINT and are rolled back at test end.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

# Register every model so Base.metadata resolves each FK when the session flushes.
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.reconciliation.refunds import detect_refunds
from modules.transactions.models import Transaction


# ---------------------------------------------------------------- helpers


async def _seed_household(db, *, currency: str = "USD") -> tuple[User, Household, BankAccount]:
    user = User(
        id=uuid.uuid4(),
        email=f"refund-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="Refund Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency=currency,
    )
    db.add(user)
    await db.flush()

    household = Household(id=uuid.uuid4(), name="Refund HH", type="individual")
    db.add(household)
    await db.flush()

    db.add(HouseholdMember(household_id=household.id, user_id=user.id, role="owner"))
    await db.flush()

    account = BankAccount(
        id=uuid.uuid4(),
        household_id=household.id,
        user_id=user.id,
        bank_name="Bank Of America",
        account_type="personal",
        currency=currency,
        is_active=True,
    )
    db.add(account)
    await db.flush()
    return user, household, account


def _tx(
    *,
    user: User,
    household: Household,
    account: BankAccount,
    amount: Decimal,
    when: datetime,
    merchant: str = "Amazon",
    currency: str | None = None,
    tx_type: str | None = None,
    transfer_pair_id: uuid.UUID | None = None,
    refund_pair_id: uuid.UUID | None = None,
) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=household.id,
        bank_account_id=account.id,
        raw_merchant_name=merchant,
        amount=amount,
        currency=currency or account.currency or "USD",
        transaction_date=when,
        source="manual",
        source_type="manual",
        status="settled",
        transaction_type=tx_type or ("income" if amount > 0 else "expense"),
        transfer_pair_id=transfer_pair_id,
        refund_pair_id=refund_pair_id,
    )


async def _reload(db, tx_id: uuid.UUID) -> Transaction:
    res = await db.execute(select(Transaction).where(Transaction.id == tx_id))
    return res.scalar_one()


# ---------------------------------------------------------------- tests


@pytest.mark.asyncio
async def test_refund_pair_same_account_opposite_signs_same_merchant_within_90d_gets_paired(db):
    user, hh, acc = await _seed_household(db)
    t0 = datetime.now(timezone.utc) - timedelta(days=10)
    charge = _tx(user=user, household=hh, account=acc, amount=Decimal("-27.43"), when=t0)
    refund = _tx(
        user=user, household=hh, account=acc, amount=Decimal("27.43"), when=t0 + timedelta(days=1)
    )
    db.add_all([charge, refund])
    await db.flush()

    pairs = await detect_refunds(db, hh.id)
    assert pairs == 1

    reloaded_charge = await _reload(db, charge.id)
    reloaded_refund = await _reload(db, refund.id)
    assert reloaded_charge.refund_pair_id is not None
    assert reloaded_charge.refund_pair_id == reloaded_refund.refund_pair_id
    # transaction_type unchanged
    assert reloaded_charge.transaction_type == "expense"
    assert reloaded_refund.transaction_type == "income"


@pytest.mark.asyncio
async def test_refund_does_not_pair_different_accounts(db):
    user, hh, acc = await _seed_household(db)
    acc2 = BankAccount(
        id=uuid.uuid4(),
        household_id=hh.id,
        user_id=user.id,
        bank_name="Chase",
        account_type="personal",
        currency="USD",
        is_active=True,
    )
    db.add(acc2)
    await db.flush()

    t0 = datetime.now(timezone.utc) - timedelta(days=5)
    charge = _tx(user=user, household=hh, account=acc, amount=Decimal("-50.00"), when=t0)
    refund = _tx(
        user=user, household=hh, account=acc2, amount=Decimal("50.00"), when=t0 + timedelta(days=1)
    )
    db.add_all([charge, refund])
    await db.flush()

    pairs = await detect_refunds(db, hh.id)
    assert pairs == 0


@pytest.mark.asyncio
async def test_refund_does_not_pair_different_currency(db):
    user, hh, acc = await _seed_household(db)
    t0 = datetime.now(timezone.utc) - timedelta(days=5)
    charge = _tx(
        user=user, household=hh, account=acc, amount=Decimal("-50.00"), when=t0, currency="USD"
    )
    refund = _tx(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("50.00"),
        when=t0 + timedelta(days=1),
        currency="EUR",
    )
    db.add_all([charge, refund])
    await db.flush()

    pairs = await detect_refunds(db, hh.id)
    assert pairs == 0


@pytest.mark.asyncio
async def test_refund_does_not_pair_outside_90d_window(db):
    user, hh, acc = await _seed_household(db)
    t0 = datetime.now(timezone.utc) - timedelta(days=130)
    charge = _tx(user=user, household=hh, account=acc, amount=Decimal("-20.00"), when=t0)
    refund = _tx(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("20.00"),
        when=t0 + timedelta(days=120),
    )
    db.add_all([charge, refund])
    await db.flush()

    pairs = await detect_refunds(db, hh.id, lookback_days=365)
    assert pairs == 0


@pytest.mark.asyncio
async def test_refund_does_not_pair_same_sign(db):
    user, hh, acc = await _seed_household(db)
    t0 = datetime.now(timezone.utc) - timedelta(days=5)
    a = _tx(user=user, household=hh, account=acc, amount=Decimal("-15.00"), when=t0)
    b = _tx(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("-15.00"),
        when=t0 + timedelta(days=1),
    )
    db.add_all([a, b])
    await db.flush()

    pairs = await detect_refunds(db, hh.id)
    assert pairs == 0


@pytest.mark.asyncio
async def test_refund_skips_already_paired(db):
    user, hh, acc = await _seed_household(db)
    t0 = datetime.now(timezone.utc) - timedelta(days=5)
    existing_pair = uuid.uuid4()
    charge = _tx(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("-77.00"),
        when=t0,
        refund_pair_id=existing_pair,
    )
    refund = _tx(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("77.00"),
        when=t0 + timedelta(days=1),
    )
    db.add_all([charge, refund])
    await db.flush()

    pairs = await detect_refunds(db, hh.id)
    assert pairs == 0

    # And again with transfer_pair_id set on the other row instead
    user2, hh2, acc2 = await _seed_household(db)
    t0 = datetime.now(timezone.utc) - timedelta(days=5)
    a = _tx(
        user=user2,
        household=hh2,
        account=acc2,
        amount=Decimal("-10.00"),
        when=t0,
        transfer_pair_id=uuid.uuid4(),
    )
    b = _tx(
        user=user2,
        household=hh2,
        account=acc2,
        amount=Decimal("10.00"),
        when=t0 + timedelta(days=1),
    )
    db.add_all([a, b])
    await db.flush()

    pairs2 = await detect_refunds(db, hh2.id)
    assert pairs2 == 0


@pytest.mark.asyncio
async def test_refund_picks_earliest_matching_refund_when_multiple(db):
    user, hh, acc = await _seed_household(db)
    t0 = datetime.now(timezone.utc) - timedelta(days=20)
    charge = _tx(user=user, household=hh, account=acc, amount=Decimal("-42.00"), when=t0)
    refund_early = _tx(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("42.00"),
        when=t0 + timedelta(days=2),
    )
    refund_late = _tx(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("42.00"),
        when=t0 + timedelta(days=10),
    )
    db.add_all([charge, refund_early, refund_late])
    await db.flush()

    pairs = await detect_refunds(db, hh.id)
    assert pairs == 1

    reloaded_charge = await _reload(db, charge.id)
    reloaded_early = await _reload(db, refund_early.id)
    reloaded_late = await _reload(db, refund_late.id)
    assert reloaded_charge.refund_pair_id is not None
    assert reloaded_charge.refund_pair_id == reloaded_early.refund_pair_id
    assert reloaded_late.refund_pair_id is None
