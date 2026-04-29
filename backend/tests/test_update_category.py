"""Tests for service.update_category, get_category_matching_count, and
update_category_bulk. Real DB via the `db` savepoint fixture, no mocks.

Mirrors test_update_merchant_name.py: validates inline-confirmation flow for
applying a category change to all matching siblings of the same merchant.
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
    get_category_matching_count,
    update_category_bulk,
)


async def _seed_user_household(db, *, currency: str = "USD"):
    user = User(
        id=uuid.uuid4(),
        email=f"cat-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="Cat Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency=currency,
    )
    db.add(user)
    await db.flush()

    hh = Household(id=uuid.uuid4(), name="Cat Hogar", type="individual")
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


def _txn(
    *,
    user,
    hh,
    account,
    merchant: str = "Best Buy",
    merchant_id=None,
    category: str | None = "Compras",
) -> Transaction:
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
        category=category,
    )


async def _reload(db, txn_id: uuid.UUID) -> Transaction | None:
    res = await db.execute(select(Transaction).where(Transaction.id == txn_id))
    return res.scalar_one_or_none()


# ─── matching-count ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_matching_count_excludes_self_target_and_user_edited(db):
    user, hh, acc = await _seed_user_household(db)
    anchor = _txn(user=user, hh=hh, account=acc, merchant="BESTBUY.COM", category="Compras")
    sib_match_a = _txn(user=user, hh=hh, account=acc, merchant="BESTBUY.COM", category="Compras")
    sib_match_b = _txn(
        user=user, hh=hh, account=acc, merchant="bestbuy.com", category="Compras"
    )  # case-insensitive
    sib_already_target = _txn(
        user=user, hh=hh, account=acc, merchant="BESTBUY.COM", category="Electrónica"
    )
    sib_user_edited = _txn(
        user=user, hh=hh, account=acc, merchant="BESTBUY.COM", category="Compras"
    )
    sib_user_edited.user_edited_fields = {"category": True}
    unrelated = _txn(user=user, hh=hh, account=acc, merchant="Starbucks", category="Compras")
    db.add_all([anchor, sib_match_a, sib_match_b, sib_already_target, sib_user_edited, unrelated])
    await db.flush()

    out = await get_category_matching_count(db, anchor.id, user.id, "Electrónica")
    assert out is not None
    # 2 siblings would be updated: sib_match_a + sib_match_b.
    # sib_already_target excluded (already at target), sib_user_edited excluded
    # (user-locked), unrelated excluded (different merchant), anchor excluded.
    assert out["count"] == 2
    assert out["raw_merchant_name"] == "BESTBUY.COM"
    assert out["merchant_id"] is None
    assert out["current_category"] == "Compras"


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

    out = await get_category_matching_count(db, txn.id, other.id, "Alimentación")
    assert out is None


# ─── bulk update ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bulk_update_applies_to_all_matching_and_marks_edited(db):
    user, hh, acc = await _seed_user_household(db)
    anchor = _txn(user=user, hh=hh, account=acc, merchant="BESTBUY.COM", category="Compras")
    sib_a = _txn(user=user, hh=hh, account=acc, merchant="BESTBUY.COM", category="Compras")
    sib_b = _txn(user=user, hh=hh, account=acc, merchant="bestbuy.com", category="Compras")
    unrelated = _txn(user=user, hh=hh, account=acc, merchant="Starbucks", category="Compras")
    db.add_all([anchor, sib_a, sib_b, unrelated])
    await db.flush()

    n = await update_category_bulk(db, anchor.id, user.id, "Electrónica")
    assert n == 3  # anchor + 2 matching siblings

    for txn_id in (anchor.id, sib_a.id, sib_b.id):
        reloaded = await _reload(db, txn_id)
        assert reloaded is not None
        assert reloaded.category == "Electrónica"
        assert (reloaded.user_edited_fields or {}).get("category") is True

    untouched = await _reload(db, unrelated.id)
    assert untouched is not None
    assert untouched.category == "Compras"
    assert (untouched.user_edited_fields or {}).get("category") is None


@pytest.mark.asyncio
async def test_bulk_update_skips_rows_already_at_target_category(db):
    user, hh, acc = await _seed_user_household(db)
    anchor = _txn(user=user, hh=hh, account=acc, merchant="BESTBUY.COM", category="Compras")
    sib_already = _txn(
        user=user, hh=hh, account=acc, merchant="BESTBUY.COM", category="Electrónica"
    )
    db.add_all([anchor, sib_already])
    await db.flush()

    # Capture the existing user_edited_fields for sib_already (should be None).
    pre_marker = (sib_already.user_edited_fields or {}).get("category")
    assert pre_marker is None

    n = await update_category_bulk(db, anchor.id, user.id, "Electrónica")
    # Only anchor is updated — sib_already already at target, skipped (no-op,
    # preserving any existing state on that row).
    assert n == 1

    reloaded_anchor = await _reload(db, anchor.id)
    assert reloaded_anchor is not None
    assert reloaded_anchor.category == "Electrónica"
    assert (reloaded_anchor.user_edited_fields or {}).get("category") is True

    reloaded_sib = await _reload(db, sib_already.id)
    assert reloaded_sib is not None
    assert reloaded_sib.category == "Electrónica"
    # Was not part of the update — marker should remain unset.
    assert (reloaded_sib.user_edited_fields or {}).get("category") is None


@pytest.mark.asyncio
async def test_bulk_update_skips_user_edited_rows(db):
    user, hh, acc = await _seed_user_household(db)
    anchor = _txn(user=user, hh=hh, account=acc, merchant="BESTBUY.COM", category="Compras")
    sib_locked = _txn(user=user, hh=hh, account=acc, merchant="BESTBUY.COM", category="Compras")
    sib_locked.user_edited_fields = {"category": True}
    db.add_all([anchor, sib_locked])
    await db.flush()

    n = await update_category_bulk(db, anchor.id, user.id, "Electrónica")
    assert n == 1  # only anchor; sib_locked preserved

    reloaded_anchor = await _reload(db, anchor.id)
    assert reloaded_anchor is not None
    assert reloaded_anchor.category == "Electrónica"

    reloaded_sib = await _reload(db, sib_locked.id)
    assert reloaded_sib is not None
    assert reloaded_sib.category == "Compras"  # untouched
    assert (reloaded_sib.user_edited_fields or {}).get("category") is True


@pytest.mark.asyncio
async def test_bulk_update_uses_original_anchor_merchant_as_match_key(db):
    """The anchor's category is mutated in-place. The match key (merchant
    name / merchant_id) must come from the anchor's pre-update identity so
    siblings are still discoverable. Mirrors the rename pattern."""
    user, hh, acc = await _seed_user_household(db)
    anchor = _txn(user=user, hh=hh, account=acc, merchant="BESTBUY.COM", category="Compras")
    sib_a = _txn(user=user, hh=hh, account=acc, merchant="BESTBUY.COM", category="Compras")
    sib_b = _txn(user=user, hh=hh, account=acc, merchant="BESTBUY.COM", category="Compras")
    db.add_all([anchor, sib_a, sib_b])
    await db.flush()

    n = await update_category_bulk(db, anchor.id, user.id, "Electrónica")
    assert n == 3
    for tid in (anchor.id, sib_a.id, sib_b.id):
        r = await _reload(db, tid)
        assert r is not None
        assert r.category == "Electrónica"


@pytest.mark.asyncio
async def test_bulk_update_matches_by_merchant_id(db):
    user, hh, acc = await _seed_user_household(db)
    merchant = Merchant(id=uuid.uuid4(), raw_name=f"raw-{uuid.uuid4().hex[:8]}")
    db.add(merchant)
    await db.flush()

    # Different raw_merchant_name strings — match must come via merchant_id.
    anchor = _txn(
        user=user,
        hh=hh,
        account=acc,
        merchant="BESTBUY.COM",
        merchant_id=merchant.id,
        category="Compras",
    )
    sib = _txn(
        user=user,
        hh=hh,
        account=acc,
        merchant="Different Spelling",
        merchant_id=merchant.id,
        category="Compras",
    )
    unrelated = _txn(user=user, hh=hh, account=acc, merchant="Starbucks", category="Compras")
    db.add_all([anchor, sib, unrelated])
    await db.flush()

    n = await update_category_bulk(db, anchor.id, user.id, "Electrónica")
    assert n == 2  # anchor + sib (linked by merchant_id)

    r_sib = await _reload(db, sib.id)
    assert r_sib is not None
    assert r_sib.category == "Electrónica"

    r_un = await _reload(db, unrelated.id)
    assert r_un is not None
    assert r_un.category == "Compras"


@pytest.mark.asyncio
async def test_bulk_update_isolated_to_household(db):
    # Household A — owner + two matching txns.
    user_a, hh_a, acc_a = await _seed_user_household(db)
    anchor = _txn(user=user_a, hh=hh_a, account=acc_a, merchant="BESTBUY.COM", category="Compras")
    sib_a = _txn(user=user_a, hh=hh_a, account=acc_a, merchant="BESTBUY.COM", category="Compras")
    db.add_all([anchor, sib_a])

    # Household B — same merchant string but different household must NOT
    # be touched.
    user_b, hh_b, acc_b = await _seed_user_household(db)
    foreign = _txn(user=user_b, hh=hh_b, account=acc_b, merchant="BESTBUY.COM", category="Compras")
    db.add(foreign)
    await db.flush()

    n = await update_category_bulk(db, anchor.id, user_a.id, "Electrónica")
    assert n == 2  # anchor + sib_a only

    r_foreign = await _reload(db, foreign.id)
    assert r_foreign is not None
    assert r_foreign.category == "Compras"
    assert (r_foreign.user_edited_fields or {}).get("category") is None


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

    out = await update_category_bulk(db, txn.id, other.id, "Electrónica")
    assert out is None
