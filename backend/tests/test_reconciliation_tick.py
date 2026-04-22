"""Tests for the reconciliation_tick orchestrator.

Covers the four passes per household:
  1. Email-after-Plaid rematch (pending email older than 5 min,
     Plaid already settled)
  2. Transfer detection
  3. Refund detection
  4. Aging pendings (>14d) into orphan when a Plaid sync has run since creation
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select, update

# Register every model so Base.metadata resolves each FK at flush time.
import modules.merchants.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.plaid.models import PlaidItem
from modules.reconciliation.tick import (
    reconciliation_tick_all_households,
    reconciliation_tick_for_household,
)
from modules.transactions.models import Transaction


# ---------------------------------------------------------------- helpers


async def _seed_household(db, *, currency: str = "USD") -> tuple[User, Household, BankAccount]:
    user = User(
        id=uuid.uuid4(),
        email=f"tick-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="Tick Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency=currency,
    )
    db.add(user)
    await db.flush()

    household = Household(id=uuid.uuid4(), name="Tick HH", type="individual")
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


def _plaid_tx(
    *,
    user,
    household,
    account,
    amount: Decimal,
    when: datetime,
    merchant: str,
    currency: str = "USD",
    status: str = "settled",
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
        status=status,
        transaction_type="expense" if amount < 0 else "income",
        plaid_transaction_id=f"plaid_{uuid.uuid4().hex[:12]}",
    )


def _email_tx(
    *,
    user,
    household,
    account,
    amount: Decimal,
    when: datetime,
    merchant: str,
    currency: str = "USD",
    status: str = "pending",
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
        source="gmail",
        source_type="email",
        status=status,
        transaction_type=tx_type,
    )


async def _backdate_created_at(db, tx_id: uuid.UUID, created_at: datetime) -> None:
    """Override the server-default created_at for deterministic aging tests."""
    await db.execute(
        update(Transaction).where(Transaction.id == tx_id).values(created_at=created_at)
    )
    await db.flush()


async def _reload(db, tx_id: uuid.UUID) -> Transaction | None:
    res = await db.execute(select(Transaction).where(Transaction.id == tx_id))
    return res.scalar_one_or_none()


# ---------------------------------------------------------------- tests


@pytest.mark.asyncio
async def test_tick_rematches_email_after_plaid_when_plaid_already_settled(db):
    user, hh, acc = await _seed_household(db)
    tx_date = datetime.now(timezone.utc) - timedelta(days=5)

    bank = _plaid_tx(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("-27.43"),
        when=tx_date,
        merchant="Uber Eats",
    )
    email = _email_tx(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("-27.43"),
        when=tx_date,
        merchant="Uber Eats",
    )
    db.add_all([bank, email])
    await db.flush()

    # Email must be older than 5 minutes to qualify for rematch.
    await _backdate_created_at(db, email.id, datetime.now(timezone.utc) - timedelta(minutes=30))

    result = await reconciliation_tick_for_household(db, hh.id)
    assert result["rematched"] == 1

    # Email row gone, Plaid row survives.
    assert await _reload(db, email.id) is None
    assert await _reload(db, bank.id) is not None


@pytest.mark.asyncio
async def test_tick_does_not_rematch_email_that_just_arrived(db):
    user, hh, acc = await _seed_household(db)
    tx_date = datetime.now(timezone.utc) - timedelta(days=1)

    bank = _plaid_tx(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("-27.43"),
        when=tx_date,
        merchant="Uber Eats",
    )
    email = _email_tx(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("-27.43"),
        when=tx_date,
        merchant="Uber Eats",
    )
    db.add_all([bank, email])
    await db.flush()
    # created_at = now by default (server_default). That's "just arrived".

    result = await reconciliation_tick_for_household(db, hh.id)
    assert result["rematched"] == 0

    # Both rows survive.
    assert await _reload(db, email.id) is not None
    assert await _reload(db, bank.id) is not None


@pytest.mark.asyncio
async def test_tick_detects_transfer_and_refund_pairs(db):
    user, hh, acc = await _seed_household(db)

    # Second account for transfer pair
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

    t0 = datetime.now(timezone.utc) - timedelta(days=3)

    # Transfer pair: opposite signs across accounts, same owner, same currency.
    tr_out = _plaid_tx(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("-500.00"),
        when=t0,
        merchant="Transfer",
    )
    tr_in = _plaid_tx(
        user=user,
        household=hh,
        account=acc2,
        amount=Decimal("500.00"),
        when=t0 + timedelta(days=1),
        merchant="Transfer",
    )

    # Refund pair: same account, same merchant, opposite signs, within 90 days.
    charge = _plaid_tx(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("-42.00"),
        when=t0,
        merchant="Amazon",
    )
    refund = _plaid_tx(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("42.00"),
        when=t0 + timedelta(days=2),
        merchant="Amazon",
    )
    db.add_all([tr_out, tr_in, charge, refund])
    await db.flush()

    result = await reconciliation_tick_for_household(db, hh.id)
    assert result["transfers"] == 1
    assert result["refunds"] == 1


@pytest.mark.asyncio
async def test_tick_ages_pending_email_older_than_14d_with_recent_sync(db):
    user, hh, acc = await _seed_household(db)
    tx_date = datetime.now(timezone.utc) - timedelta(days=16)

    email = _email_tx(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("-12.00"),
        when=tx_date,
        merchant="Lost Merchant",
    )
    db.add(email)
    await db.flush()
    created_at = datetime.now(timezone.utc) - timedelta(days=15)
    await _backdate_created_at(db, email.id, created_at)

    item = PlaidItem(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=hh.id,
        plaid_item_id=f"pi_{uuid.uuid4().hex[:8]}",
        access_token_enc="enc",
        institution_id="ins_1",
        institution_name="BofA",
        last_sync_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db.add(item)
    await db.flush()

    result = await reconciliation_tick_for_household(db, hh.id)
    assert result["orphaned"] == 1

    reloaded = await _reload(db, email.id)
    assert reloaded is not None
    assert reloaded.status == "orphan"
    assert reloaded.orphaned_at is not None


@pytest.mark.asyncio
async def test_tick_does_not_age_when_no_sync_since_creation(db):
    user, hh, acc = await _seed_household(db)
    tx_date = datetime.now(timezone.utc) - timedelta(days=16)

    email = _email_tx(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("-12.00"),
        when=tx_date,
        merchant="Lost Merchant",
    )
    db.add(email)
    await db.flush()
    created_at = datetime.now(timezone.utc) - timedelta(days=15)
    await _backdate_created_at(db, email.id, created_at)

    # Last sync is OLDER than tx creation — bank may be down.
    item = PlaidItem(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=hh.id,
        plaid_item_id=f"pi_{uuid.uuid4().hex[:8]}",
        access_token_enc="enc",
        institution_id="ins_1",
        institution_name="BofA",
        last_sync_at=datetime.now(timezone.utc) - timedelta(days=20),
    )
    db.add(item)
    await db.flush()

    result = await reconciliation_tick_for_household(db, hh.id)
    assert result["orphaned"] == 0

    reloaded = await _reload(db, email.id)
    assert reloaded is not None
    assert reloaded.status == "pending"
    assert reloaded.orphaned_at is None


@pytest.mark.asyncio
async def test_tick_all_households_aggregates(db):
    # Household A
    user_a, hh_a, acc_a = await _seed_household(db)
    tx_date_a = datetime.now(timezone.utc) - timedelta(days=4)
    bank_a = _plaid_tx(
        user=user_a,
        household=hh_a,
        account=acc_a,
        amount=Decimal("-15.00"),
        when=tx_date_a,
        merchant="Netflix",
    )
    email_a = _email_tx(
        user=user_a,
        household=hh_a,
        account=acc_a,
        amount=Decimal("-15.00"),
        when=tx_date_a,
        merchant="Netflix",
    )
    db.add_all([bank_a, email_a])
    await db.flush()
    await _backdate_created_at(db, email_a.id, datetime.now(timezone.utc) - timedelta(minutes=30))

    # Household B
    user_b, hh_b, acc_b = await _seed_household(db)
    tx_date_b = datetime.now(timezone.utc) - timedelta(days=2)
    bank_b = _plaid_tx(
        user=user_b,
        household=hh_b,
        account=acc_b,
        amount=Decimal("-88.88"),
        when=tx_date_b,
        merchant="Spotify",
    )
    email_b = _email_tx(
        user=user_b,
        household=hh_b,
        account=acc_b,
        amount=Decimal("-88.88"),
        when=tx_date_b,
        merchant="Spotify",
    )
    db.add_all([bank_b, email_b])
    await db.flush()
    await _backdate_created_at(db, email_b.id, datetime.now(timezone.utc) - timedelta(minutes=30))

    # reconciliation_tick_all_households commits between households — the
    # savepoint fixture's outer transaction still rolls everything back at teardown.
    totals = await reconciliation_tick_all_households(db)
    assert totals["rematched"] >= 2


@pytest.mark.asyncio
async def test_tick_detects_wallet_pairs(db):
    """The tick runs the wallet pass and reports pairs in its return dict."""
    user, hh, bofa = await _seed_household(db)
    venmo = BankAccount(
        id=uuid.uuid4(),
        household_id=hh.id,
        user_id=user.id,
        bank_name="Venmo",
        account_type="personal",
        currency="USD",
        is_active=True,
    )
    db.add(venmo)
    await db.flush()

    # Use recent dates — the tick's wallet pass uses lookback_days=30.
    day0 = datetime.now(timezone.utc) - timedelta(days=10)
    venmo_tx = _plaid_tx(
        user=user,
        household=hh,
        account=venmo,
        amount=Decimal("-30.90"),
        when=day0,
        merchant="Nicolas Celasco",
    )
    bofa_tx = _plaid_tx(
        user=user,
        household=hh,
        account=bofa,
        amount=Decimal("-30.90"),
        when=day0 + timedelta(days=3),
        merchant="VENMO *PAYMENT",
    )
    db.add_all([venmo_tx, bofa_tx])
    await db.flush()

    totals = await reconciliation_tick_for_household(db, hh.id)
    assert totals["wallet_pairs"] == 1

    await db.refresh(venmo_tx)
    await db.refresh(bofa_tx)
    assert bofa_tx.transaction_type == "transfer"
    assert venmo_tx.transaction_type == "expense"
    assert bofa_tx.transfer_pair_id == venmo_tx.transfer_pair_id
