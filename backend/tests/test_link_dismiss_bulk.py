"""Tests for Tasks 3.2 / 3.3 / 3.4 — link, dismiss, and bulk-action service.

Real DB via the `db` savepoint fixture. Ownership is enforced in SQL —
tests with cross-user rows verify both the status code and the absence of
side effects.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.transactions.models import Transaction
from modules.transactions.service import (
    ServiceError,
    bulk_action,
    dismiss_transaction,
    link_email_to_bank,
)


# ---------------------------------------------------------------- helpers


async def _seed_user_household(db, *, currency: str = "USD"):
    user = User(
        id=uuid.uuid4(),
        email=f"ld-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="LD Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency=currency,
    )
    db.add(user)
    await db.flush()

    hh = Household(id=uuid.uuid4(), name="LD Hogar", type="individual")
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


def _email(
    *,
    user,
    hh,
    account,
    amount: Decimal,
    when: datetime,
    currency: str = "USD",
    category: str | None = "Food",
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
        category=category,
    )


def _bank(
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
        raw_merchant_name="STARBUCKS #1234",
        amount=amount,
        currency=currency,
        transaction_date=when,
        source="plaid",
        source_type="plaid",
        status="settled",
        transaction_type="expense",
        transfer_pair_id=transfer_pair_id,
    )


async def _reload(db, tx_id: uuid.UUID) -> Transaction | None:
    res = await db.execute(select(Transaction).where(Transaction.id == tx_id))
    return res.scalar_one_or_none()


# ---------------------------------------------------------------- Task 3.2 — link


@pytest.mark.asyncio
async def test_link_happy_path(db):
    user, hh, account = await _seed_user_household(db)
    when = datetime.now(timezone.utc) - timedelta(days=1)

    email = _email(
        user=user,
        hh=hh,
        account=account,
        amount=Decimal("-27.43"),
        when=when,
        category="Food",
    )
    bank = _bank(
        user=user,
        hh=hh,
        account=account,
        amount=Decimal("-27.43"),
        when=when,
    )
    bank.category = None
    db.add_all([email, bank])
    await db.flush()

    result = await link_email_to_bank(db, user.id, email.id, bank.id)

    # Email row is deleted.
    assert (await _reload(db, email.id)) is None
    # Bank row keeps its id and now carries the email's enrichment.
    refreshed = await _reload(db, bank.id)
    assert refreshed is not None
    assert refreshed.category == "Food"
    assert result["id"] == bank.id


@pytest.mark.asyncio
async def test_link_403_when_cross_user(db):
    user_a, hh_a, acc_a = await _seed_user_household(db)
    user_b, hh_b, acc_b = await _seed_user_household(db)
    when = datetime.now(timezone.utc) - timedelta(days=1)

    email_a = _email(user=user_a, hh=hh_a, account=acc_a, amount=Decimal("-27.43"), when=when)
    bank_b = _bank(user=user_b, hh=hh_b, account=acc_b, amount=Decimal("-27.43"), when=when)
    db.add_all([email_a, bank_b])
    await db.flush()

    with pytest.raises(ServiceError) as exc:
        await link_email_to_bank(db, user_a.id, email_a.id, bank_b.id)
    assert exc.value.code == "forbidden"

    # No side effects.
    assert (await _reload(db, email_a.id)) is not None
    assert (await _reload(db, bank_b.id)) is not None


@pytest.mark.asyncio
async def test_link_409_when_bank_row_already_paired(db):
    user, hh, account = await _seed_user_household(db)
    when = datetime.now(timezone.utc) - timedelta(days=1)

    email = _email(user=user, hh=hh, account=account, amount=Decimal("-27.43"), when=when)
    bank = _bank(
        user=user,
        hh=hh,
        account=account,
        amount=Decimal("-27.43"),
        when=when,
        transfer_pair_id=uuid.uuid4(),
    )
    db.add_all([email, bank])
    await db.flush()

    with pytest.raises(ServiceError) as exc:
        await link_email_to_bank(db, user.id, email.id, bank.id)
    assert exc.value.code == "conflict"


# ---------------------------------------------------------------- Task 3.3 — dismiss


@pytest.mark.asyncio
async def test_dismiss_sets_status_to_orphan(db):
    user, hh, account = await _seed_user_household(db)
    when = datetime.now(timezone.utc) - timedelta(days=1)

    email = _email(user=user, hh=hh, account=account, amount=Decimal("-27.43"), when=when)
    db.add(email)
    await db.flush()

    await dismiss_transaction(db, user.id, email.id)

    refreshed = await _reload(db, email.id)
    assert refreshed is not None
    assert refreshed.status == "orphan"
    assert refreshed.dismissed_by_user is True
    assert refreshed.orphaned_at is not None


@pytest.mark.asyncio
async def test_dismiss_403_when_not_owner(db):
    user_a, hh_a, acc_a = await _seed_user_household(db)
    user_b, _, _ = await _seed_user_household(db)
    when = datetime.now(timezone.utc) - timedelta(days=1)

    email_a = _email(user=user_a, hh=hh_a, account=acc_a, amount=Decimal("-27.43"), when=when)
    db.add(email_a)
    await db.flush()

    with pytest.raises(ServiceError) as exc:
        await dismiss_transaction(db, user_b.id, email_a.id)
    assert exc.value.code == "forbidden"

    # No side effect.
    refreshed = await _reload(db, email_a.id)
    assert refreshed.status == "pending"
    assert refreshed.dismissed_by_user is False


@pytest.mark.asyncio
async def test_dismiss_409_when_already_orphan(db):
    user, hh, account = await _seed_user_household(db)
    when = datetime.now(timezone.utc) - timedelta(days=1)

    email = _email(user=user, hh=hh, account=account, amount=Decimal("-27.43"), when=when)
    email.status = "orphan"
    db.add(email)
    await db.flush()

    with pytest.raises(ServiceError) as exc:
        await dismiss_transaction(db, user.id, email.id)
    assert exc.value.code == "conflict"


# ---------------------------------------------------------------- Task 3.4 — bulk-action


@pytest.mark.asyncio
async def test_bulk_dismiss_happy_path(db):
    user, hh, account = await _seed_user_household(db)
    when = datetime.now(timezone.utc) - timedelta(days=1)

    rows = [
        _email(user=user, hh=hh, account=account, amount=Decimal("-10.00"), when=when)
        for _ in range(3)
    ]
    db.add_all(rows)
    await db.flush()
    ids = [r.id for r in rows]

    processed = await bulk_action(db, user.id, ids, "dismiss")
    assert processed == 3
    for tx_id in ids:
        r = await _reload(db, tx_id)
        assert r is not None
        assert r.status == "orphan"
        assert r.dismissed_by_user is True


@pytest.mark.asyncio
async def test_bulk_delete_happy_path(db):
    user, hh, account = await _seed_user_household(db)
    when = datetime.now(timezone.utc) - timedelta(days=1)

    rows = [
        _email(user=user, hh=hh, account=account, amount=Decimal("-10.00"), when=when)
        for _ in range(3)
    ]
    db.add_all(rows)
    await db.flush()
    ids = [r.id for r in rows]

    processed = await bulk_action(db, user.id, ids, "delete")
    assert processed == 3
    for tx_id in ids:
        assert (await _reload(db, tx_id)) is None


@pytest.mark.asyncio
async def test_bulk_action_403_if_any_id_belongs_to_another_user(db):
    user_a, hh_a, acc_a = await _seed_user_household(db)
    user_b, hh_b, acc_b = await _seed_user_household(db)
    when = datetime.now(timezone.utc) - timedelta(days=1)

    own_rows = [
        _email(user=user_a, hh=hh_a, account=acc_a, amount=Decimal("-10.00"), when=when)
        for _ in range(2)
    ]
    foreign = _email(user=user_b, hh=hh_b, account=acc_b, amount=Decimal("-10.00"), when=when)
    db.add_all([*own_rows, foreign])
    await db.flush()

    ids = [own_rows[0].id, own_rows[1].id, foreign.id]
    with pytest.raises(ServiceError) as exc:
        await bulk_action(db, user_a.id, ids, "dismiss")
    assert exc.value.code == "forbidden"

    # No side effects on any of the three.
    for tx_id in ids:
        r = await _reload(db, tx_id)
        assert r is not None
        assert r.status == "pending"
        assert r.dismissed_by_user is False


@pytest.mark.asyncio
async def test_bulk_action_422_when_over_100_ids(db):
    user, _, _ = await _seed_user_household(db)
    ids = [uuid.uuid4() for _ in range(101)]

    with pytest.raises(ServiceError) as exc:
        await bulk_action(db, user.id, ids, "dismiss")
    assert exc.value.code == "too_many"
