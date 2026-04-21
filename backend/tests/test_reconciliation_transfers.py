"""Tests for cross-account transfer pair detection.

Covers the user_id and currency equality guards added to detect_transfers so
that (a) two household members' independent same-amount transactions are never
paired as a transfer, and (b) a CLP 10.000 and a USD 10.000 are never paired.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.reconciliation.transfers import detect_transfers
from modules.transactions.models import Transaction


async def _seed_user(db, *, currency: str = "USD") -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"xfer-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="Xfer Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency=currency,
    )
    db.add(user)
    await db.flush()
    return user


async def _seed_household(db, owner: User) -> Household:
    household = Household(id=uuid.uuid4(), name="Xfer HH", type="individual")
    db.add(household)
    await db.flush()
    db.add(HouseholdMember(household_id=household.id, user_id=owner.id, role="owner"))
    await db.flush()
    return household


async def _seed_account(
    db,
    household: Household,
    user: User,
    *,
    bank_name: str,
    currency: str = "USD",
) -> BankAccount:
    account = BankAccount(
        id=uuid.uuid4(),
        household_id=household.id,
        user_id=user.id,
        bank_name=bank_name,
        account_type="personal",
        currency=currency,
        is_active=True,
    )
    db.add(account)
    await db.flush()
    return account


def _txn(
    *,
    user: User,
    household: Household,
    account: BankAccount,
    amount: Decimal,
    currency: str = "USD",
    date: datetime,
) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=household.id,
        bank_account_id=account.id,
        raw_merchant_name="Internal Transfer",
        amount=amount,
        currency=currency,
        transaction_date=date,
        transaction_type="expense" if amount < 0 else "income",
        status="settled",
        source="plaid",
        source_type="plaid",
    )


@pytest.mark.asyncio
async def test_transfer_pairs_same_user_different_accounts(db):
    user = await _seed_user(db)
    hh = await _seed_household(db, user)
    checking = await _seed_account(db, hh, user, bank_name="BofA")
    savings = await _seed_account(db, hh, user, bank_name="BofA Savings")

    today = datetime.now(timezone.utc)
    out = _txn(user=user, household=hh, account=checking, amount=Decimal("-500"), date=today)
    inc = _txn(
        user=user,
        household=hh,
        account=savings,
        amount=Decimal("500"),
        date=today + timedelta(days=1),
    )
    db.add_all([out, inc])
    await db.flush()

    pairs = await detect_transfers(db, hh.id, lookback_days=5)
    assert pairs == 1

    await db.refresh(out)
    await db.refresh(inc)
    assert out.transfer_pair_id is not None
    assert out.transfer_pair_id == inc.transfer_pair_id
    assert out.transaction_type == "transfer"
    assert inc.transaction_type == "transfer"


@pytest.mark.asyncio
async def test_transfer_does_not_pair_cross_user_in_same_household(db):
    owner = await _seed_user(db)
    partner = await _seed_user(db)
    hh = await _seed_household(db, owner)
    db.add(HouseholdMember(household_id=hh.id, user_id=partner.id, role="member"))
    await db.flush()

    owner_acc = await _seed_account(db, hh, owner, bank_name="BofA Owner")
    partner_acc = await _seed_account(db, hh, partner, bank_name="BofA Partner")

    today = datetime.now(timezone.utc)
    # Same amount, opposite signs, different accounts, different users -> NOT a transfer.
    out = _txn(user=owner, household=hh, account=owner_acc, amount=Decimal("-500"), date=today)
    inc = _txn(user=partner, household=hh, account=partner_acc, amount=Decimal("500"), date=today)
    db.add_all([out, inc])
    await db.flush()

    pairs = await detect_transfers(db, hh.id, lookback_days=5)
    assert pairs == 0

    await db.refresh(out)
    await db.refresh(inc)
    assert out.transfer_pair_id is None
    assert inc.transfer_pair_id is None
    assert out.transaction_type == "expense"
    assert inc.transaction_type == "income"


@pytest.mark.asyncio
async def test_transfer_does_not_pair_different_currencies(db):
    user = await _seed_user(db)
    hh = await _seed_household(db, user)
    usd_acc = await _seed_account(db, hh, user, bank_name="BofA USD", currency="USD")
    clp_acc = await _seed_account(db, hh, user, bank_name="Santander CLP", currency="CLP")

    today = datetime.now(timezone.utc)
    out = _txn(
        user=user, household=hh, account=usd_acc, amount=Decimal("-500"), currency="USD", date=today
    )
    inc = _txn(
        user=user, household=hh, account=clp_acc, amount=Decimal("500"), currency="CLP", date=today
    )
    db.add_all([out, inc])
    await db.flush()

    pairs = await detect_transfers(db, hh.id, lookback_days=5)
    assert pairs == 0

    await db.refresh(out)
    await db.refresh(inc)
    assert out.transfer_pair_id is None
    assert inc.transfer_pair_id is None
