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
from modules.transactions.service import (
    get_merchant_name_matching_count,
    update_merchant_name,
    update_merchant_name_bulk,
)


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


# ─── Bulk rename: matching-count + apply_to_all_matching ──────────────────


@pytest.mark.asyncio
async def test_matching_count_excludes_self_and_user_edited(db):
    user, hh, acc = await _seed_user_household(db)
    anchor = _txn(user=user, hh=hh, account=acc, merchant="BESTBUY.COM")
    sib_a = _txn(user=user, hh=hh, account=acc, merchant="BESTBUY.COM")
    sib_b = _txn(user=user, hh=hh, account=acc, merchant="bestbuy.com")  # case-insensitive
    sib_edited = _txn(user=user, hh=hh, account=acc, merchant="BESTBUY.COM")
    sib_edited.user_edited_fields = {"merchant_name": True}
    unrelated = _txn(user=user, hh=hh, account=acc, merchant="Starbucks")
    db.add_all([anchor, sib_a, sib_b, sib_edited, unrelated])
    await db.flush()

    out = await get_merchant_name_matching_count(db, anchor.id, user.id)
    assert out is not None
    # 2 siblings (sib_a + sib_b) — anchor self excluded, sib_edited excluded,
    # unrelated different name excluded.
    assert out["count"] == 2
    assert out["raw_merchant_name"] == "BESTBUY.COM"
    assert out["merchant_id"] is None


@pytest.mark.asyncio
async def test_matching_count_404_when_caller_outside_household(db):
    user, hh, acc = await _seed_user_household(db)
    txn = _txn(user=user, hh=hh, account=acc)
    db.add(txn)
    await db.flush()

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

    out = await get_merchant_name_matching_count(db, txn.id, other.id)
    assert out is None


@pytest.mark.asyncio
async def test_bulk_update_applies_to_all_matching_and_marks_edited(db):
    user, hh, acc = await _seed_user_household(db)
    anchor = _txn(user=user, hh=hh, account=acc, merchant="BESTBUY.COM")
    sib_a = _txn(user=user, hh=hh, account=acc, merchant="BESTBUY.COM")
    sib_b = _txn(user=user, hh=hh, account=acc, merchant="bestbuy.com")
    unrelated = _txn(user=user, hh=hh, account=acc, merchant="Starbucks")
    db.add_all([anchor, sib_a, sib_b, unrelated])
    await db.flush()

    n = await update_merchant_name_bulk(db, anchor.id, user.id, raw_merchant_name="Best Buy")
    assert n == 3  # anchor + 2 matching siblings

    for txn_id in (anchor.id, sib_a.id, sib_b.id):
        reloaded = await _reload(db, txn_id)
        assert reloaded is not None
        assert reloaded.raw_merchant_name == "Best Buy"
        assert (reloaded.user_edited_fields or {}).get("merchant_name") is True

    untouched = await _reload(db, unrelated.id)
    assert untouched is not None
    assert untouched.raw_merchant_name == "Starbucks"
    assert (untouched.user_edited_fields or {}).get("merchant_name") is None


@pytest.mark.asyncio
async def test_bulk_update_skips_user_edited_rows(db):
    user, hh, acc = await _seed_user_household(db)
    anchor = _txn(user=user, hh=hh, account=acc, merchant="BESTBUY.COM")
    sib_edited = _txn(user=user, hh=hh, account=acc, merchant="BESTBUY.COM")
    sib_edited.user_edited_fields = {"merchant_name": True}
    db.add_all([anchor, sib_edited])
    await db.flush()

    n = await update_merchant_name_bulk(db, anchor.id, user.id, raw_merchant_name="Best Buy")
    assert n == 1  # only anchor; sib_edited preserved

    reloaded_anchor = await _reload(db, anchor.id)
    assert reloaded_anchor is not None
    assert reloaded_anchor.raw_merchant_name == "Best Buy"

    reloaded_sib = await _reload(db, sib_edited.id)
    assert reloaded_sib is not None
    assert reloaded_sib.raw_merchant_name == "BESTBUY.COM"  # untouched
    assert (reloaded_sib.user_edited_fields or {}).get("merchant_name") is True


@pytest.mark.asyncio
async def test_bulk_update_uses_original_anchor_name_as_match_key(db):
    """Anchor's `raw_merchant_name` is mutated in-place during the bulk
    operation. The match key must be captured BEFORE the mutation, otherwise
    the anchor would no longer match its siblings (the new name doesn't
    exist on them yet)."""
    user, hh, acc = await _seed_user_household(db)
    anchor = _txn(user=user, hh=hh, account=acc, merchant="BESTBUY.COM")
    sib_a = _txn(user=user, hh=hh, account=acc, merchant="BESTBUY.COM")
    sib_b = _txn(user=user, hh=hh, account=acc, merchant="BESTBUY.COM")
    db.add_all([anchor, sib_a, sib_b])
    await db.flush()

    n = await update_merchant_name_bulk(db, anchor.id, user.id, raw_merchant_name="Best Buy")
    # All three end up renamed — anchor + both siblings.
    assert n == 3
    for tid in (anchor.id, sib_a.id, sib_b.id):
        r = await _reload(db, tid)
        assert r is not None
        assert r.raw_merchant_name == "Best Buy"


@pytest.mark.asyncio
async def test_bulk_update_matches_by_merchant_id(db):
    user, hh, acc = await _seed_user_household(db)
    merchant = Merchant(id=uuid.uuid4(), raw_name=f"raw-{uuid.uuid4().hex[:8]}")
    db.add(merchant)
    await db.flush()

    # Different raw_merchant_name strings — match must come via merchant_id.
    anchor = _txn(user=user, hh=hh, account=acc, merchant="BESTBUY.COM", merchant_id=merchant.id)
    sib = _txn(
        user=user,
        hh=hh,
        account=acc,
        merchant="Different Spelling",
        merchant_id=merchant.id,
    )
    unrelated = _txn(user=user, hh=hh, account=acc, merchant="Starbucks")
    db.add_all([anchor, sib, unrelated])
    await db.flush()

    n = await update_merchant_name_bulk(db, anchor.id, user.id, raw_merchant_name="Best Buy")
    assert n == 2  # anchor + sib (linked by merchant_id)

    r_sib = await _reload(db, sib.id)
    assert r_sib is not None
    assert r_sib.raw_merchant_name == "Best Buy"

    r_un = await _reload(db, unrelated.id)
    assert r_un is not None
    assert r_un.raw_merchant_name == "Starbucks"


@pytest.mark.asyncio
async def test_bulk_update_isolated_to_household(db):
    # Household A — owner + two matching txns.
    user_a, hh_a, acc_a = await _seed_user_household(db)
    anchor = _txn(user=user_a, hh=hh_a, account=acc_a, merchant="BESTBUY.COM")
    sib_a = _txn(user=user_a, hh=hh_a, account=acc_a, merchant="BESTBUY.COM")
    db.add_all([anchor, sib_a])

    # Household B — same merchant string but different household must NOT
    # be touched.
    user_b, hh_b, acc_b = await _seed_user_household(db)
    foreign = _txn(user=user_b, hh=hh_b, account=acc_b, merchant="BESTBUY.COM")
    db.add(foreign)
    await db.flush()

    n = await update_merchant_name_bulk(db, anchor.id, user_a.id, raw_merchant_name="Best Buy")
    assert n == 2  # anchor + sib_a only

    r_foreign = await _reload(db, foreign.id)
    assert r_foreign is not None
    assert r_foreign.raw_merchant_name == "BESTBUY.COM"
    assert (r_foreign.user_edited_fields or {}).get("merchant_name") is None


@pytest.mark.asyncio
async def test_bulk_update_404_when_caller_outside_household(db):
    user, hh, acc = await _seed_user_household(db)
    txn = _txn(user=user, hh=hh, account=acc)
    db.add(txn)
    await db.flush()

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

    out = await update_merchant_name_bulk(db, txn.id, other.id, raw_merchant_name="Hacked")
    assert out is None
