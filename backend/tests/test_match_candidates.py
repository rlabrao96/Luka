"""Tests for GET /transactions/{pending_id}/match-candidates (Task 3.1).

Use real DB via the `db` savepoint fixture. Exercises the service layer
directly (ownership + SQL filters) — authorization lives in SQL, not Python.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

# Ensure all relationship-target models are registered.
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.transactions.models import Transaction
from modules.transactions.service import (
    get_match_candidates,
    link_email_to_bank,
    ServiceError,
)


# ---------------------------------------------------------------- helpers


async def _seed_user_household(db, *, currency: str = "USD"):
    user = User(
        id=uuid.uuid4(),
        email=f"mc-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="MatchCand Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency=currency,
    )
    db.add(user)
    await db.flush()

    hh = Household(id=uuid.uuid4(), name="MC Hogar", type="individual")
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


def _pending_email(
    *, user, hh, account, amount: Decimal, when: datetime, currency: str = "USD"
) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=hh.id,
        bank_account_id=account.id if account else None,
        raw_merchant_name="Starbucks",
        amount=amount,
        currency=currency,
        transaction_date=when,
        source="gmail",
        source_type="email",
        status="pending",
        transaction_type="expense",
    )


def _plaid_settled(
    *,
    user,
    hh,
    account,
    amount: Decimal,
    when: datetime,
    currency: str = "USD",
    transfer_pair_id: uuid.UUID | None = None,
) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=hh.id,
        bank_account_id=account.id,
        raw_merchant_name="Starbucks",
        amount=amount,
        currency=currency,
        transaction_date=when,
        source="plaid",
        source_type="plaid",
        status="settled",
        transaction_type="expense",
        transfer_pair_id=transfer_pair_id,
    )


# ---------------------------------------------------------------- tests


@pytest.mark.asyncio
async def test_returns_ranked_candidates_scoped_to_household_and_currency(db):
    user, hh, account = await _seed_user_household(db, currency="USD")
    when = datetime.now(timezone.utc) - timedelta(days=1)

    pending = _pending_email(user=user, hh=hh, account=account, amount=Decimal("-27.43"), when=when)
    db.add(pending)

    # Three valid candidates at differing date proximity.
    c_close = _plaid_settled(user=user, hh=hh, account=account, amount=Decimal("-27.43"), when=when)
    c_mid = _plaid_settled(
        user=user,
        hh=hh,
        account=account,
        amount=Decimal("-27.43"),
        when=when + timedelta(days=2),
    )
    c_far = _plaid_settled(
        user=user,
        hh=hh,
        account=account,
        amount=Decimal("-27.43"),
        when=when - timedelta(days=5),
    )
    # Different currency — excluded.
    clp_row = _plaid_settled(
        user=user,
        hh=hh,
        account=account,
        amount=Decimal("-27.43"),
        when=when,
        currency="CLP",
    )
    db.add_all([c_close, c_mid, c_far, clp_row])
    await db.flush()

    results = await get_match_candidates(db, user.id, pending.id, window_days=7)
    ids = [r["id"] for r in results]

    assert clp_row.id not in ids, "Wrong currency must not be returned"
    assert ids[:3] == [
        c_close.id,
        c_mid.id,
        c_far.id,
    ], f"Expected ranking by date proximity, got {ids}"


@pytest.mark.asyncio
async def test_excludes_already_paired_rows(db):
    user, hh, account = await _seed_user_household(db, currency="USD")
    when = datetime.now(timezone.utc) - timedelta(days=1)

    pending = _pending_email(user=user, hh=hh, account=account, amount=Decimal("-27.43"), when=when)
    paired = _plaid_settled(
        user=user,
        hh=hh,
        account=account,
        amount=Decimal("-27.43"),
        when=when,
        transfer_pair_id=uuid.uuid4(),
    )
    db.add_all([pending, paired])
    await db.flush()

    results = await get_match_candidates(db, user.id, pending.id, window_days=7)
    assert paired.id not in [r["id"] for r in results]


@pytest.mark.asyncio
async def test_filters_by_2pct_amount_tolerance(db):
    user, hh, account = await _seed_user_household(db, currency="USD")
    when = datetime.now(timezone.utc) - timedelta(days=1)

    pending = _pending_email(user=user, hh=hh, account=account, amount=Decimal("-27.43"), when=when)
    # 30 vs 27.43 — |30 - 27.43| = 2.57 > 0.02 * 27.43 = 0.5486
    out_of_tolerance = _plaid_settled(
        user=user, hh=hh, account=account, amount=Decimal("-30.00"), when=when
    )
    # Inside tolerance: 27.43 * 0.02 = 0.5486 → 27.80 is just inside (|0.37| <= 0.5486)
    inside = _plaid_settled(user=user, hh=hh, account=account, amount=Decimal("-27.80"), when=when)
    db.add_all([pending, out_of_tolerance, inside])
    await db.flush()

    results = await get_match_candidates(db, user.id, pending.id, window_days=7)
    ids = [r["id"] for r in results]
    assert out_of_tolerance.id not in ids
    assert inside.id in ids


@pytest.mark.asyncio
async def test_404_if_pending_id_not_owned_by_caller(db):
    user_a, hh_a, account_a = await _seed_user_household(db, currency="USD")
    user_b, hh_b, _account_b = await _seed_user_household(db, currency="USD")
    when = datetime.now(timezone.utc)

    # Pending row belongs to user A
    pending_a = _pending_email(
        user=user_a, hh=hh_a, account=account_a, amount=Decimal("-10.00"), when=when
    )
    db.add(pending_a)
    await db.flush()

    with pytest.raises(ServiceError) as exc:
        await get_match_candidates(db, user_b.id, pending_a.id, window_days=7)
    assert exc.value.code == "not_found"


def _plaid_pending(
    *,
    user,
    hh,
    account,
    amount: Decimal,
    when: datetime,
    currency: str = "USD",
) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=hh.id,
        bank_account_id=account.id,
        raw_merchant_name="Starbucks",
        amount=amount,
        currency=currency,
        transaction_date=when,
        source="plaid",
        source_type="plaid",
        status="pending",
        transaction_type="expense",
    )


@pytest.mark.asyncio
async def test_includes_pending_plaid_rows_alongside_settled(db):
    """The most common duplicate: email pending + Plaid pending. Both must surface."""
    user, hh, account = await _seed_user_household(db, currency="USD")
    when = datetime.now(timezone.utc) - timedelta(days=1)

    pending_email = _pending_email(
        user=user, hh=hh, account=account, amount=Decimal("-27.43"), when=when
    )
    settled_bank = _plaid_settled(
        user=user, hh=hh, account=account, amount=Decimal("-27.43"), when=when
    )
    pending_bank = _plaid_pending(
        user=user, hh=hh, account=account, amount=Decimal("-27.43"), when=when
    )
    db.add_all([pending_email, settled_bank, pending_bank])
    await db.flush()

    results = await get_match_candidates(db, user.id, pending_email.id, window_days=7)
    ids = {r["id"] for r in results}
    assert settled_bank.id in ids
    assert pending_bank.id in ids
    statuses = {r["id"]: r["status"] for r in results}
    assert statuses[pending_bank.id] == "pending"
    assert statuses[settled_bank.id] == "settled"


@pytest.mark.asyncio
async def test_intent_transfer_returns_opposite_sign_different_account(db):
    """intent='transfer' surfaces only candidates that pass manual-transfer
    preconditions: opposite sign, different account, same currency, bank-only,
    unpaired, ±window_days."""
    user, hh, acct_a = await _seed_user_household(db, currency="USD")
    # Second account in same household
    acct_b = BankAccount(
        id=uuid.uuid4(),
        household_id=hh.id,
        user_id=user.id,
        bank_name="AmEx",
        account_name="Card",
        account_type="personal",
        currency="USD",
        is_active=True,
    )
    db.add(acct_b)
    await db.flush()

    when = datetime.now(timezone.utc)
    # Source row (settled bank tx, outflow on acct_a)
    source = _plaid_settled(user=user, hh=hh, account=acct_a, amount=Decimal("-200.00"), when=when)
    # Valid transfer counterpart (inflow on acct_b)
    counterpart = _plaid_settled(
        user=user, hh=hh, account=acct_b, amount=Decimal("200.00"), when=when
    )
    # Same-account row → excluded
    same_acct = _plaid_settled(
        user=user, hh=hh, account=acct_a, amount=Decimal("200.00"), when=when
    )
    # Same-sign row → excluded
    same_sign = _plaid_settled(
        user=user, hh=hh, account=acct_b, amount=Decimal("-200.00"), when=when
    )
    db.add_all([source, counterpart, same_acct, same_sign])
    await db.flush()

    results = await get_match_candidates(db, user.id, source.id, window_days=7, intent="transfer")
    ids = {r["id"] for r in results}
    assert counterpart.id in ids
    assert same_acct.id not in ids
    assert same_sign.id not in ids


@pytest.mark.asyncio
async def test_intent_transfer_excludes_already_paired(db):
    user, hh, acct_a = await _seed_user_household(db, currency="USD")
    acct_b = BankAccount(
        id=uuid.uuid4(),
        household_id=hh.id,
        user_id=user.id,
        bank_name="AmEx",
        account_name="Card",
        account_type="personal",
        currency="USD",
        is_active=True,
    )
    db.add(acct_b)
    await db.flush()

    when = datetime.now(timezone.utc)
    source = _plaid_settled(user=user, hh=hh, account=acct_a, amount=Decimal("-50.00"), when=when)
    paired = _plaid_settled(
        user=user,
        hh=hh,
        account=acct_b,
        amount=Decimal("50.00"),
        when=when,
        transfer_pair_id=uuid.uuid4(),
    )
    db.add_all([source, paired])
    await db.flush()

    results = await get_match_candidates(db, user.id, source.id, window_days=7, intent="transfer")
    assert paired.id not in [r["id"] for r in results]


@pytest.mark.asyncio
async def test_link_email_to_pending_plaid_consolidates_and_keeps_pending_status(db):
    """Pending email + pending Plaid: link should keep the Plaid row (still pending),
    apply email enrichment (category), and delete the email row."""
    user, hh, account = await _seed_user_household(db, currency="USD")
    when = datetime.now(timezone.utc) - timedelta(days=1)

    email_row = _pending_email(
        user=user, hh=hh, account=account, amount=Decimal("-27.43"), when=when
    )
    email_row.category = "Food"
    bank_row = _plaid_pending(
        user=user, hh=hh, account=account, amount=Decimal("-27.43"), when=when
    )
    bank_row.category = None
    db.add_all([email_row, bank_row])
    await db.flush()

    from sqlalchemy import select as _select

    result = await link_email_to_bank(db, user.id, email_row.id, bank_row.id)

    # Email row is gone.
    refreshed_email = (
        await db.execute(_select(Transaction).where(Transaction.id == email_row.id))
    ).scalar_one_or_none()
    assert refreshed_email is None

    # Bank row kept, still pending, enriched with email category.
    refreshed_bank = (
        await db.execute(_select(Transaction).where(Transaction.id == bank_row.id))
    ).scalar_one_or_none()
    assert refreshed_bank is not None
    assert refreshed_bank.id == bank_row.id
    assert refreshed_bank.status == "pending"
    assert refreshed_bank.category == "Food"
    assert result["id"] == bank_row.id

    # Idempotency: relinking after email is gone should 404, not corrupt state.
    with pytest.raises(ServiceError) as exc:
        await link_email_to_bank(db, user.id, email_row.id, bank_row.id)
    assert exc.value.code == "not_found"
