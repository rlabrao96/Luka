"""Tests for wallet funding-pair detection (Venmo / PayPal / CashApp)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.reconciliation.wallets import detect_wallet_pairs, is_wallet_account
from modules.transactions.models import Transaction


async def _seed_user(db, *, currency: str = "USD") -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"wallet-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="Wallet Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency=currency,
    )
    db.add(user)
    await db.flush()
    return user


async def _seed_household(db, owner: User) -> Household:
    hh = Household(id=uuid.uuid4(), name="Wallet HH", type="individual")
    db.add(hh)
    await db.flush()
    db.add(HouseholdMember(household_id=hh.id, user_id=owner.id, role="owner"))
    await db.flush()
    return hh


async def _seed_account(
    db,
    household: Household,
    user: User,
    *,
    bank_name: str,
    account_kind: str | None = None,
    currency: str = "USD",
) -> BankAccount:
    acct = BankAccount(
        id=uuid.uuid4(),
        household_id=household.id,
        user_id=user.id,
        bank_name=bank_name,
        account_type="personal",
        account_kind=account_kind,
        currency=currency,
        is_active=True,
    )
    db.add(acct)
    await db.flush()
    return acct


def _txn(
    *,
    user: User,
    household: Household,
    account: BankAccount,
    amount: Decimal,
    merchant: str,
    currency: str = "USD",
    date: datetime,
) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=household.id,
        bank_account_id=account.id,
        raw_merchant_name=merchant,
        amount=amount,
        currency=currency,
        transaction_date=date,
        transaction_type="expense" if amount < 0 else "income",
        status="settled",
        source="plaid",
        source_type="plaid",
    )


@pytest.mark.asyncio
async def test_is_wallet_account_detects_venmo_by_bank_name(db):
    user = await _seed_user(db)
    hh = await _seed_household(db, user)
    venmo = await _seed_account(db, hh, user, bank_name="Venmo")
    bofa = await _seed_account(
        db, hh, user, bank_name="Bank of America", account_kind="checking_account"
    )
    assert is_wallet_account(venmo) is True
    assert is_wallet_account(bofa) is False


@pytest.mark.asyncio
async def test_is_wallet_account_detects_by_account_kind(db):
    user = await _seed_user(db)
    hh = await _seed_household(db, user)
    wallet = await _seed_account(db, hh, user, bank_name="SomeThirdParty", account_kind="wallet")
    assert is_wallet_account(wallet) is True


@pytest.mark.asyncio
async def test_same_sign_funding_pair_matches_bofa_to_venmo(db):
    """The Feb 6 / Feb 9 Nicolas Celasco case from the spec."""
    user = await _seed_user(db)
    hh = await _seed_household(db, user)
    bofa = await _seed_account(
        db, hh, user, bank_name="Bank of America", account_kind="checking_account"
    )
    venmo = await _seed_account(db, hh, user, bank_name="Venmo")

    feb6 = datetime(2026, 2, 6, tzinfo=timezone.utc)
    feb9 = datetime(2026, 2, 9, tzinfo=timezone.utc)
    venmo_tx = _txn(
        user=user,
        household=hh,
        account=venmo,
        amount=Decimal("-30.90"),
        merchant="Nicolas Celasco",
        date=feb6,
    )
    bofa_tx = _txn(
        user=user,
        household=hh,
        account=bofa,
        amount=Decimal("-30.90"),
        merchant="VENMO *PAYMENT",
        date=feb9,
    )
    db.add_all([venmo_tx, bofa_tx])
    await db.flush()

    pairs = await detect_wallet_pairs(db, hh.id, lookback_days=365 * 10)
    assert pairs == 1

    await db.refresh(venmo_tx)
    await db.refresh(bofa_tx)
    assert venmo_tx.transfer_pair_id is not None
    assert venmo_tx.transfer_pair_id == bofa_tx.transfer_pair_id
    assert bofa_tx.transaction_type == "transfer"
    assert venmo_tx.transaction_type == "expense"


@pytest.mark.asyncio
async def test_wallet_bank_name_with_suffix_still_matches_bare_merchant(db):
    """Plaid returns bank_name='Venmo - Personal' but BofA merchant is just 'Venmo'.

    The merchant gate must match on the short wallet token ('venmo'), not on
    the full wallet bank_name.
    """
    user = await _seed_user(db)
    hh = await _seed_household(db, user)
    bofa = await _seed_account(
        db, hh, user, bank_name="Bank of America", account_kind="checking_account"
    )
    venmo = await _seed_account(
        db, hh, user, bank_name="Venmo - Personal", account_kind="checking_account"
    )

    day0 = datetime(2026, 3, 2, tzinfo=timezone.utc)
    venmo_tx = _txn(
        user=user,
        household=hh,
        account=venmo,
        amount=Decimal("-240.00"),
        merchant="Some Counterparty",
        date=day0,
    )
    bofa_tx = _txn(
        user=user,
        household=hh,
        account=bofa,
        amount=Decimal("-240.00"),
        merchant="Venmo",
        date=day0 + timedelta(days=2),
    )
    db.add_all([venmo_tx, bofa_tx])
    await db.flush()

    pairs = await detect_wallet_pairs(db, hh.id, lookback_days=365 * 10)
    assert pairs == 1
    await db.refresh(bofa_tx)
    assert bofa_tx.transaction_type == "transfer"


@pytest.mark.asyncio
async def test_opposite_sign_cashout_within_5_days_matches(db):
    """Venmo cash-out to BofA that takes 4 calendar days to settle."""
    user = await _seed_user(db)
    hh = await _seed_household(db, user)
    bofa = await _seed_account(
        db, hh, user, bank_name="Bank of America", account_kind="checking_account"
    )
    venmo = await _seed_account(db, hh, user, bank_name="Venmo")

    day0 = datetime(2026, 3, 1, tzinfo=timezone.utc)
    venmo_out = _txn(
        user=user,
        household=hh,
        account=venmo,
        amount=Decimal("-50.00"),
        merchant="Transfer to Bank",
        date=day0,
    )
    bofa_in = _txn(
        user=user,
        household=hh,
        account=bofa,
        amount=Decimal("50.00"),
        merchant="VENMO CASHOUT",
        date=day0 + timedelta(days=4),
    )
    db.add_all([venmo_out, bofa_in])
    await db.flush()

    pairs = await detect_wallet_pairs(db, hh.id, lookback_days=365 * 10)
    assert pairs == 1

    await db.refresh(venmo_out)
    await db.refresh(bofa_in)
    assert venmo_out.transfer_pair_id == bofa_in.transfer_pair_id
    assert bofa_in.transaction_type == "transfer"
    assert venmo_out.transaction_type == "expense"


@pytest.mark.asyncio
async def test_paypal_merchant_without_paypal_account_does_not_pair(db):
    """Merchant name alone must never pair without a connected wallet account."""
    user = await _seed_user(db)
    hh = await _seed_household(db, user)
    bofa = await _seed_account(
        db, hh, user, bank_name="Bank of America", account_kind="checking_account"
    )

    day0 = datetime(2026, 2, 10, tzinfo=timezone.utc)
    bofa_tx = _txn(
        user=user,
        household=hh,
        account=bofa,
        amount=Decimal("-20.00"),
        merchant="PAYPAL *SOMETHING",
        date=day0,
    )
    unrelated = _txn(
        user=user,
        household=hh,
        account=bofa,
        amount=Decimal("-20.00"),
        merchant="Coffee Shop",
        date=day0 + timedelta(days=1),
    )
    db.add_all([bofa_tx, unrelated])
    await db.flush()

    pairs = await detect_wallet_pairs(db, hh.id, lookback_days=365 * 10)
    assert pairs == 0
    await db.refresh(bofa_tx)
    assert bofa_tx.transfer_pair_id is None
    assert bofa_tx.transaction_type == "expense"


@pytest.mark.asyncio
async def test_partial_topup_does_not_pair(db):
    """BofA tops up $50 but Venmo spends only $30.90 — amounts differ."""
    user = await _seed_user(db)
    hh = await _seed_household(db, user)
    bofa = await _seed_account(
        db, hh, user, bank_name="Bank of America", account_kind="checking_account"
    )
    venmo = await _seed_account(db, hh, user, bank_name="Venmo")

    day0 = datetime(2026, 2, 6, tzinfo=timezone.utc)
    venmo_tx = _txn(
        user=user,
        household=hh,
        account=venmo,
        amount=Decimal("-30.90"),
        merchant="Nicolas Celasco",
        date=day0,
    )
    bofa_tx = _txn(
        user=user,
        household=hh,
        account=bofa,
        amount=Decimal("-50.00"),
        merchant="VENMO *PAYMENT",
        date=day0 + timedelta(days=3),
    )
    db.add_all([venmo_tx, bofa_tx])
    await db.flush()

    pairs = await detect_wallet_pairs(db, hh.id, lookback_days=365 * 10)
    assert pairs == 0


@pytest.mark.asyncio
async def test_venmo_only_payment_with_no_bofa_leg_stays_unchanged(db):
    """Payment covered by Venmo balance — only the Venmo row exists."""
    user = await _seed_user(db)
    hh = await _seed_household(db, user)
    venmo = await _seed_account(db, hh, user, bank_name="Venmo")

    venmo_tx = _txn(
        user=user,
        household=hh,
        account=venmo,
        amount=Decimal("-10.00"),
        merchant="Alejandro Carrillo",
        date=datetime(2026, 2, 6, tzinfo=timezone.utc),
    )
    db.add(venmo_tx)
    await db.flush()

    pairs = await detect_wallet_pairs(db, hh.id, lookback_days=365 * 10)
    assert pairs == 0
    await db.refresh(venmo_tx)
    assert venmo_tx.transfer_pair_id is None
    assert venmo_tx.transaction_type == "expense"


@pytest.mark.asyncio
async def test_already_paired_rows_are_skipped(db):
    user = await _seed_user(db)
    hh = await _seed_household(db, user)
    bofa = await _seed_account(
        db, hh, user, bank_name="Bank of America", account_kind="checking_account"
    )
    venmo = await _seed_account(db, hh, user, bank_name="Venmo")

    existing_pair = uuid.uuid4()
    day0 = datetime(2026, 2, 6, tzinfo=timezone.utc)
    venmo_tx = _txn(
        user=user,
        household=hh,
        account=venmo,
        amount=Decimal("-30.90"),
        merchant="Nicolas",
        date=day0,
    )
    venmo_tx.transfer_pair_id = existing_pair
    bofa_tx = _txn(
        user=user,
        household=hh,
        account=bofa,
        amount=Decimal("-30.90"),
        merchant="VENMO",
        date=day0 + timedelta(days=2),
    )
    db.add_all([venmo_tx, bofa_tx])
    await db.flush()

    pairs = await detect_wallet_pairs(db, hh.id, lookback_days=365 * 10)
    assert pairs == 0


@pytest.mark.asyncio
async def test_cross_household_isolation(db):
    user_a = await _seed_user(db)
    user_b = await _seed_user(db)
    hh_a = await _seed_household(db, user_a)
    hh_b = await _seed_household(db, user_b)

    venmo_a = await _seed_account(db, hh_a, user_a, bank_name="Venmo")
    bofa_b = await _seed_account(
        db, hh_b, user_b, bank_name="Bank of America", account_kind="checking_account"
    )

    day0 = datetime(2026, 2, 6, tzinfo=timezone.utc)
    venmo_tx = _txn(
        user=user_a,
        household=hh_a,
        account=venmo_a,
        amount=Decimal("-30.90"),
        merchant="Nicolas",
        date=day0,
    )
    bofa_tx = _txn(
        user=user_b,
        household=hh_b,
        account=bofa_b,
        amount=Decimal("-30.90"),
        merchant="VENMO",
        date=day0 + timedelta(days=2),
    )
    db.add_all([venmo_tx, bofa_tx])
    await db.flush()

    assert await detect_wallet_pairs(db, hh_a.id, lookback_days=365 * 10) == 0
    assert await detect_wallet_pairs(db, hh_b.id, lookback_days=365 * 10) == 0


@pytest.mark.asyncio
async def test_cross_currency_does_not_pair(db):
    user = await _seed_user(db)
    hh = await _seed_household(db, user)
    bofa_usd = await _seed_account(
        db,
        hh,
        user,
        bank_name="Bank of America",
        currency="USD",
        account_kind="checking_account",
    )
    venmo_clp = await _seed_account(db, hh, user, bank_name="Venmo", currency="CLP")

    day0 = datetime(2026, 2, 6, tzinfo=timezone.utc)
    venmo_tx = _txn(
        user=user,
        household=hh,
        account=venmo_clp,
        amount=Decimal("-3090"),
        merchant="Nicolas",
        currency="CLP",
        date=day0,
    )
    bofa_tx = _txn(
        user=user,
        household=hh,
        account=bofa_usd,
        amount=Decimal("-3090"),
        merchant="VENMO",
        currency="USD",
        date=day0 + timedelta(days=2),
    )
    db.add_all([venmo_tx, bofa_tx])
    await db.flush()

    pairs = await detect_wallet_pairs(db, hh.id, lookback_days=365 * 10)
    assert pairs == 0
