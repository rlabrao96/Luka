"""Tests for service.update_merchant_name and the PATCH /transactions/{id}/merchant-name
endpoint. Real DB via the `db` savepoint fixture, no mocks.

Verifies:
- Successful rename stamps `user_edited_fields["merchant_name"] = True`.
- Caller outside the transaction's household → 404.
- Both fields supplied → both updated.
- Only `raw_merchant_name` supplied → `merchant_id` unchanged.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

import modules.merchants.models  # noqa: F401  (ensure mappers configured)
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.merchants.models import Merchant
from modules.transactions.models import Transaction
from modules.transactions.service import update_merchant_name


async def _seed_user_household(db, *, currency: str = "USD"):
    user = User(
        id=uuid.uuid4(),
        email=f"mn-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="MN Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency=currency,
    )
    db.add(user)
    await db.flush()

    hh = Household(id=uuid.uuid4(), name="MN Hogar", type="individual")
    db.add(hh)
    await db.flush()

    db.add(HouseholdMember(household_id=hh.id, user_id=user.id, role="owner"))
    await db.flush()

    account = BankAccount(
        id=uuid.uuid4(),
        household_id=hh.id,
        user_id=user.id,
        bank_name="Bank Of America",
        account_name="Checking",
        account_type="personal",
        currency=currency,
        is_active=True,
    )
    db.add(account)
    await db.flush()
    return user, hh, account


def _txn(*, user, hh, account, merchant: str = "Old Name", merchant_id=None) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=hh.id,
        bank_account_id=account.id,
        merchant_id=merchant_id,
        raw_merchant_name=merchant,
        amount=Decimal("-12.50"),
        currency="USD",
        transaction_date=datetime.now(timezone.utc),
        source="gmail",
        source_type="email",
        status="pending",
        transaction_type="expense",
    )


async def _reload(db, txn_id: uuid.UUID) -> Transaction | None:
    res = await db.execute(select(Transaction).where(Transaction.id == txn_id))
    return res.scalar_one_or_none()


@pytest.mark.asyncio
async def test_rename_sets_marker_and_updates_name(db):
    user, hh, acc = await _seed_user_household(db)
    txn = _txn(user=user, hh=hh, account=acc, merchant="Starbux")
    db.add(txn)
    await db.flush()

    ok = await update_merchant_name(db, txn.id, user.id, raw_merchant_name="Starbucks Reserve")
    assert ok is True

    reloaded = await _reload(db, txn.id)
    assert reloaded is not None
    assert reloaded.raw_merchant_name == "Starbucks Reserve"
    assert (reloaded.user_edited_fields or {}).get("merchant_name") is True


@pytest.mark.asyncio
async def test_rename_404_when_caller_outside_household(db):
    user, hh, acc = await _seed_user_household(db)
    txn = _txn(user=user, hh=hh, account=acc)
    db.add(txn)
    await db.flush()

    # Foreign user — not a member of the txn's household.
    other = User(
        id=uuid.uuid4(),
        email=f"foreign-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="Foreign",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency="USD",
    )
    db.add(other)
    await db.flush()

    ok = await update_merchant_name(db, txn.id, other.id, raw_merchant_name="Hacked")
    assert ok is False

    reloaded = await _reload(db, txn.id)
    assert reloaded is not None
    assert reloaded.raw_merchant_name == "Old Name"
    assert (reloaded.user_edited_fields or {}).get("merchant_name") is None


@pytest.mark.asyncio
async def test_rename_with_both_fields_updates_both(db):
    user, hh, acc = await _seed_user_household(db)
    txn = _txn(user=user, hh=hh, account=acc, merchant="Old", merchant_id=None)
    db.add(txn)
    await db.flush()

    # Seed a merchant row to reference.
    merchant = Merchant(
        id=uuid.uuid4(),
        raw_name=f"raw-{uuid.uuid4().hex[:8]}",
    )
    db.add(merchant)
    await db.flush()

    ok = await update_merchant_name(
        db,
        txn.id,
        user.id,
        raw_merchant_name="Starbucks",
        merchant_id=merchant.id,
    )
    assert ok is True

    reloaded = await _reload(db, txn.id)
    assert reloaded is not None
    assert reloaded.raw_merchant_name == "Starbucks"
    assert reloaded.merchant_id == merchant.id
    assert (reloaded.user_edited_fields or {}).get("merchant_name") is True


@pytest.mark.asyncio
async def test_rename_only_raw_does_not_touch_merchant_id(db):
    user, hh, acc = await _seed_user_household(db)
    existing_merchant = Merchant(
        id=uuid.uuid4(),
        raw_name=f"raw-{uuid.uuid4().hex[:8]}",
    )
    db.add(existing_merchant)
    await db.flush()

    txn = _txn(
        user=user,
        hh=hh,
        account=acc,
        merchant="Old",
        merchant_id=existing_merchant.id,
    )
    db.add(txn)
    await db.flush()

    ok = await update_merchant_name(db, txn.id, user.id, raw_merchant_name="Renamed")
    assert ok is True

    reloaded = await _reload(db, txn.id)
    assert reloaded is not None
    assert reloaded.raw_merchant_name == "Renamed"
    # merchant_id must remain pointing at the original merchant row.
    assert reloaded.merchant_id == existing_merchant.id
    assert (reloaded.user_edited_fields or {}).get("merchant_name") is True
