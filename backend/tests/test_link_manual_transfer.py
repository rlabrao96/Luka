"""Tests for service.link_manual_transfer.

Covers the manual transfer-pair link flow used by the settled-row "Vincular"
action in RecentTransactions: the user picks two own-account bank rows the
auto-detector missed (e.g. CC payment outflow on BoA + matching inflow on
the AmEx card) and links them by hand.

Real DB via the `db` savepoint fixture, no mocks.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.transactions.models import Transaction
from modules.transactions.service import link_manual_transfer, ServiceError


async def _seed_user_household(db, *, currency: str = "USD"):
    user = User(
        id=uuid.uuid4(),
        email=f"lt-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="LT Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency=currency,
    )
    db.add(user)
    await db.flush()
    hh = Household(id=uuid.uuid4(), name="LT Hogar", type="individual")
    db.add(hh)
    await db.flush()
    db.add(HouseholdMember(household_id=hh.id, user_id=user.id, role="owner"))
    await db.flush()
    return user, hh


async def _seed_account(db, user, hh, *, name="Checking", currency="USD"):
    account = BankAccount(
        id=uuid.uuid4(),
        household_id=hh.id,
        user_id=user.id,
        bank_name=f"Bank-{name}",
        account_name=name,
        account_type="personal",
        currency=currency,
        is_active=True,
    )
    db.add(account)
    await db.flush()
    return account


def _bank_tx(
    *,
    user,
    hh,
    account,
    amount: Decimal,
    when: datetime,
    currency: str = "USD",
    source_type: str = "plaid",
    source: str = "plaid",
    transfer_pair_id: uuid.UUID | None = None,
    refund_pair_id: uuid.UUID | None = None,
) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=hh.id,
        bank_account_id=account.id,
        raw_merchant_name="Transfer leg",
        amount=amount,
        currency=currency,
        transaction_date=when,
        source=source,
        source_type=source_type,
        status="settled",
        transaction_type="expense",
        transfer_pair_id=transfer_pair_id,
        refund_pair_id=refund_pair_id,
    )


# ── happy path ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_happy_path_pairs_two_own_account_bank_legs(db):
    user, hh = await _seed_user_household(db)
    acct_a = await _seed_account(db, user, hh, name="Checking")
    acct_b = await _seed_account(db, user, hh, name="Credit Card")
    when = datetime.now(timezone.utc)

    out_leg = _bank_tx(user=user, hh=hh, account=acct_a, amount=Decimal("-250.00"), when=when)
    in_leg = _bank_tx(user=user, hh=hh, account=acct_b, amount=Decimal("250.00"), when=when)
    db.add_all([out_leg, in_leg])
    await db.flush()

    result = await link_manual_transfer(db, out_leg.id, in_leg.id, user.id)

    assert result["transfer_pair_id"]
    refreshed = (
        (await db.execute(select(Transaction).where(Transaction.id.in_([out_leg.id, in_leg.id]))))
        .scalars()
        .all()
    )
    pair_ids = {r.transfer_pair_id for r in refreshed}
    assert len(pair_ids) == 1 and None not in pair_ids
    types = {r.transaction_type for r in refreshed}
    assert types == {"transfer"}
    for r in refreshed:
        assert r.user_edited_fields.get("transaction_type") is True


# ── precondition rejections ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rejects_same_account(db):
    user, hh = await _seed_user_household(db)
    acct = await _seed_account(db, user, hh)
    when = datetime.now(timezone.utc)
    a = _bank_tx(user=user, hh=hh, account=acct, amount=Decimal("-100.00"), when=when)
    b = _bank_tx(user=user, hh=hh, account=acct, amount=Decimal("100.00"), when=when)
    db.add_all([a, b])
    await db.flush()

    with pytest.raises(ServiceError) as exc:
        await link_manual_transfer(db, a.id, b.id, user.id)
    assert exc.value.code == "invalid_action"


@pytest.mark.asyncio
async def test_rejects_same_sign(db):
    user, hh = await _seed_user_household(db)
    acct_a = await _seed_account(db, user, hh, name="A")
    acct_b = await _seed_account(db, user, hh, name="B")
    when = datetime.now(timezone.utc)
    a = _bank_tx(user=user, hh=hh, account=acct_a, amount=Decimal("-100.00"), when=when)
    b = _bank_tx(user=user, hh=hh, account=acct_b, amount=Decimal("-100.00"), when=when)
    db.add_all([a, b])
    await db.flush()

    with pytest.raises(ServiceError) as exc:
        await link_manual_transfer(db, a.id, b.id, user.id)
    assert exc.value.code == "invalid_action"


@pytest.mark.asyncio
async def test_rejects_currency_mismatch(db):
    user, hh = await _seed_user_household(db)
    acct_a = await _seed_account(db, user, hh, name="A", currency="USD")
    acct_b = await _seed_account(db, user, hh, name="B", currency="CLP")
    when = datetime.now(timezone.utc)
    a = _bank_tx(
        user=user, hh=hh, account=acct_a, amount=Decimal("-100.00"), when=when, currency="USD"
    )
    b = _bank_tx(
        user=user, hh=hh, account=acct_b, amount=Decimal("100.00"), when=when, currency="CLP"
    )
    db.add_all([a, b])
    await db.flush()

    with pytest.raises(ServiceError) as exc:
        await link_manual_transfer(db, a.id, b.id, user.id)
    assert exc.value.code == "invalid_action"


@pytest.mark.asyncio
async def test_rejects_already_paired(db):
    user, hh = await _seed_user_household(db)
    acct_a = await _seed_account(db, user, hh, name="A")
    acct_b = await _seed_account(db, user, hh, name="B")
    when = datetime.now(timezone.utc)
    existing_pair = uuid.uuid4()
    a = _bank_tx(
        user=user,
        hh=hh,
        account=acct_a,
        amount=Decimal("-100.00"),
        when=when,
        transfer_pair_id=existing_pair,
    )
    b = _bank_tx(user=user, hh=hh, account=acct_b, amount=Decimal("100.00"), when=when)
    db.add_all([a, b])
    await db.flush()

    with pytest.raises(ServiceError) as exc:
        await link_manual_transfer(db, a.id, b.id, user.id)
    assert exc.value.code == "conflict"


@pytest.mark.asyncio
async def test_rejects_email_source(db):
    user, hh = await _seed_user_household(db)
    acct_a = await _seed_account(db, user, hh, name="A")
    acct_b = await _seed_account(db, user, hh, name="B")
    when = datetime.now(timezone.utc)
    a = _bank_tx(
        user=user,
        hh=hh,
        account=acct_a,
        amount=Decimal("-100.00"),
        when=when,
        source="gmail",
        source_type="email",
    )
    b = _bank_tx(user=user, hh=hh, account=acct_b, amount=Decimal("100.00"), when=when)
    db.add_all([a, b])
    await db.flush()

    with pytest.raises(ServiceError) as exc:
        await link_manual_transfer(db, a.id, b.id, user.id)
    assert exc.value.code == "invalid_action"


@pytest.mark.asyncio
async def test_cross_household_rejection(db):
    """Caller is not a member of the second row's household → not_found."""
    user_a, hh_a = await _seed_user_household(db)
    user_b, hh_b = await _seed_user_household(db)
    acct_a1 = await _seed_account(db, user_a, hh_a, name="A1")
    acct_b1 = await _seed_account(db, user_b, hh_b, name="B1")
    when = datetime.now(timezone.utc)
    a = _bank_tx(user=user_a, hh=hh_a, account=acct_a1, amount=Decimal("-100.00"), when=when)
    b = _bank_tx(user=user_b, hh=hh_b, account=acct_b1, amount=Decimal("100.00"), when=when)
    db.add_all([a, b])
    await db.flush()

    with pytest.raises(ServiceError) as exc:
        await link_manual_transfer(db, a.id, b.id, user_a.id)
    assert exc.value.code == "not_found"


@pytest.mark.asyncio
async def test_rejects_self_pair(db):
    user, hh = await _seed_user_household(db)
    acct = await _seed_account(db, user, hh)
    when = datetime.now(timezone.utc)
    a = _bank_tx(user=user, hh=hh, account=acct, amount=Decimal("-100.00"), when=when)
    db.add(a)
    await db.flush()

    with pytest.raises(ServiceError) as exc:
        await link_manual_transfer(db, a.id, a.id, user.id)
    assert exc.value.code == "invalid_action"
