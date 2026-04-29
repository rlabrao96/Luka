"""Tests for the credit-suggestion auto-detector + endpoints.

Real-DB tests via the savepoint `db` fixture (no mocks).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

# Register every model so Base.metadata resolves each FK.
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.notifications.models import Notification
from modules.reconciliation.credit_suggestions import (
    NOTIFICATION_TYPE,
    emit_credit_suggestions_for_household,
    find_credit_suggestions,
    is_credit_pattern_name,
)
from modules.transactions.models import Transaction


# ----------------------------------------------------------------- regex


@pytest.mark.parametrize(
    "name",
    [
        "Platinum Resy Credit",
        "Statement Credit",
        "Cashback Reward",
        "SAKS Credit",
        "Uber Cash Credit",
        "Reembolso digital",
        "Equinox Credit",
        "Streaming Credit",
        "Walmart+ Credit",
        "Cash Back",
        "Adjustment",
        "Reward",
    ],
)
def test_is_credit_pattern_name_positive(name: str):
    assert is_credit_pattern_name(name) is True


@pytest.mark.parametrize(
    "name",
    [
        "Best Buy",
        "Trader Joe's",
        "Amazon",
        "Bank of America Credit Card",
        "Credit Card Statement",
        "",
        None,
        "Apple",
    ],
)
def test_is_credit_pattern_name_negative(name):
    assert is_credit_pattern_name(name) is False


# ----------------------------------------------------------------- helpers


async def _seed(db, *, currency: str = "USD") -> tuple[User, Household, BankAccount]:
    user = User(
        id=uuid.uuid4(),
        email=f"credit-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="Credit Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency=currency,
    )
    db.add(user)
    await db.flush()
    hh = Household(id=uuid.uuid4(), name="Credit HH", type="individual")
    db.add(hh)
    await db.flush()
    db.add(HouseholdMember(household_id=hh.id, user_id=user.id, role="owner"))
    await db.flush()
    acc = BankAccount(
        id=uuid.uuid4(),
        household_id=hh.id,
        user_id=user.id,
        bank_name="Amex",
        account_type="personal",
        currency=currency,
        is_active=True,
    )
    db.add(acc)
    await db.flush()
    return user, hh, acc


def _tx(
    *,
    user,
    hh,
    acc,
    amount: Decimal,
    when: datetime,
    merchant: str,
    source_type: str = "plaid",
    transfer_pair_id=None,
    refund_pair_id=None,
    reimbursement_group_id=None,
) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=hh.id,
        bank_account_id=acc.id,
        raw_merchant_name=merchant,
        amount=amount,
        currency=acc.currency,
        transaction_date=when,
        source="plaid",
        source_type=source_type,
        status="settled",
        transaction_type=("income" if amount > 0 else "expense"),
        transfer_pair_id=transfer_pair_id,
        refund_pair_id=refund_pair_id,
        reimbursement_group_id=reimbursement_group_id,
    )


# ----------------------------------------------------------------- detector


@pytest.mark.asyncio
async def test_detects_obvious_credit_pair(db):
    user, hh, acc = await _seed(db)
    now = datetime.now(timezone.utc)
    charge = _tx(
        user=user,
        hh=hh,
        acc=acc,
        amount=Decimal("-81.92"),
        when=now - timedelta(days=4),
        merchant="Ambrosia",
    )
    credit = _tx(
        user=user,
        hh=hh,
        acc=acc,
        amount=Decimal("81.92"),
        when=now - timedelta(days=1),
        merchant="Platinum Resy Credit",
    )
    db.add_all([charge, credit])
    await db.flush()

    suggestions = await find_credit_suggestions(db, hh.id)
    assert len(suggestions) == 1
    assert suggestions[0].credit_txn_id == credit.id
    assert suggestions[0].counterpart_txn_id == charge.id


@pytest.mark.asyncio
async def test_skips_when_zero_candidates(db):
    user, hh, acc = await _seed(db)
    now = datetime.now(timezone.utc)
    credit = _tx(
        user=user,
        hh=hh,
        acc=acc,
        amount=Decimal("50.00"),
        when=now - timedelta(days=1),
        merchant="Statement Credit",
    )
    db.add(credit)
    await db.flush()
    assert await find_credit_suggestions(db, hh.id) == []


@pytest.mark.asyncio
async def test_skips_when_multiple_candidates_ambiguous(db):
    user, hh, acc = await _seed(db)
    now = datetime.now(timezone.utc)
    c1 = _tx(
        user=user,
        hh=hh,
        acc=acc,
        amount=Decimal("-25.00"),
        when=now - timedelta(days=10),
        merchant="Coffee Shop",
    )
    c2 = _tx(
        user=user,
        hh=hh,
        acc=acc,
        amount=Decimal("-25.00"),
        when=now - timedelta(days=5),
        merchant="Other Cafe",
    )
    credit = _tx(
        user=user,
        hh=hh,
        acc=acc,
        amount=Decimal("25.00"),
        when=now - timedelta(days=1),
        merchant="Statement Credit",
    )
    db.add_all([c1, c2, credit])
    await db.flush()
    assert await find_credit_suggestions(db, hh.id) == []


@pytest.mark.asyncio
async def test_skips_when_credit_older_than_30d(db):
    user, hh, acc = await _seed(db)
    now = datetime.now(timezone.utc)
    charge = _tx(
        user=user,
        hh=hh,
        acc=acc,
        amount=Decimal("-40.00"),
        when=now - timedelta(days=45),
        merchant="Ambrosia",
    )
    credit = _tx(
        user=user,
        hh=hh,
        acc=acc,
        amount=Decimal("40.00"),
        when=now - timedelta(days=40),
        merchant="Platinum Resy Credit",
    )
    db.add_all([charge, credit])
    await db.flush()
    assert await find_credit_suggestions(db, hh.id) == []


@pytest.mark.asyncio
async def test_skips_when_either_row_already_paired(db):
    user, hh, acc = await _seed(db)
    now = datetime.now(timezone.utc)
    pair_id = uuid.uuid4()
    charge = _tx(
        user=user,
        hh=hh,
        acc=acc,
        amount=Decimal("-12.00"),
        when=now - timedelta(days=4),
        merchant="Ambrosia",
        refund_pair_id=pair_id,
    )
    credit = _tx(
        user=user,
        hh=hh,
        acc=acc,
        amount=Decimal("12.00"),
        when=now - timedelta(days=1),
        merchant="Statement Credit",
    )
    db.add_all([charge, credit])
    await db.flush()
    assert await find_credit_suggestions(db, hh.id) == []


@pytest.mark.asyncio
async def test_emit_is_idempotent(db):
    user, hh, acc = await _seed(db)
    now = datetime.now(timezone.utc)
    charge = _tx(
        user=user,
        hh=hh,
        acc=acc,
        amount=Decimal("-81.92"),
        when=now - timedelta(days=4),
        merchant="Ambrosia",
    )
    credit = _tx(
        user=user,
        hh=hh,
        acc=acc,
        amount=Decimal("81.92"),
        when=now - timedelta(days=1),
        merchant="Platinum Resy Credit",
    )
    db.add_all([charge, credit])
    await db.flush()

    r1 = await emit_credit_suggestions_for_household(db, hh.id)
    assert r1["created"] == 1
    r2 = await emit_credit_suggestions_for_household(db, hh.id)
    assert r2["created"] == 0

    res = await db.execute(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.type == NOTIFICATION_TYPE,
        )
    )
    assert len(res.scalars().all()) == 1


@pytest.mark.asyncio
async def test_auto_resolves_when_paired_elsewhere(db):
    user, hh, acc = await _seed(db)
    now = datetime.now(timezone.utc)
    charge = _tx(
        user=user,
        hh=hh,
        acc=acc,
        amount=Decimal("-15.00"),
        when=now - timedelta(days=4),
        merchant="Ambrosia",
    )
    credit = _tx(
        user=user,
        hh=hh,
        acc=acc,
        amount=Decimal("15.00"),
        when=now - timedelta(days=1),
        merchant="Platinum Resy Credit",
    )
    db.add_all([charge, credit])
    await db.flush()

    r1 = await emit_credit_suggestions_for_household(db, hh.id)
    assert r1["created"] == 1

    # Simulate the credit row getting paired some other way.
    credit.reimbursement_group_id = uuid.uuid4()
    await db.flush()

    r2 = await emit_credit_suggestions_for_household(db, hh.id)
    assert r2["auto_resolved"] >= 1

    res = await db.execute(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.type == NOTIFICATION_TYPE,
        )
    )
    notifs = res.scalars().all()
    assert all(n.status == "dismissed" for n in notifs)


# ----------------------------------------------------------------- endpoints


def _override_user(app, user: User, db):
    """Wire the FastAPI app's dependencies to use this test user + savepoint db."""
    from core.database import get_db
    from core.security import get_current_user

    async def _fake_db():
        yield db

    async def _fake_user():
        return user

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _fake_user


@pytest.mark.asyncio
async def test_confirm_endpoint_links_reimbursement_and_marks_actioned(app, db):
    user, hh, acc = await _seed(db)
    now = datetime.now(timezone.utc)
    charge = _tx(
        user=user,
        hh=hh,
        acc=acc,
        amount=Decimal("-81.92"),
        when=now - timedelta(days=4),
        merchant="Ambrosia",
    )
    credit = _tx(
        user=user,
        hh=hh,
        acc=acc,
        amount=Decimal("81.92"),
        when=now - timedelta(days=1),
        merchant="Platinum Resy Credit",
    )
    db.add_all([charge, credit])
    await db.flush()

    await emit_credit_suggestions_for_household(db, hh.id)
    res = await db.execute(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.type == NOTIFICATION_TYPE,
        )
    )
    notif = res.scalar_one()

    _override_user(app, user, db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(f"/transactions/credit-suggestions/{notif.id}/confirm")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("reimbursement_group_id")

    await db.refresh(notif)
    await db.refresh(charge)
    await db.refresh(credit)
    assert notif.status == "actioned"
    assert charge.reimbursement_group_id is not None
    assert charge.reimbursement_group_id == credit.reimbursement_group_id


@pytest.mark.asyncio
async def test_dismiss_endpoint_marks_dismissed(app, db):
    user, hh, acc = await _seed(db)
    now = datetime.now(timezone.utc)
    charge = _tx(
        user=user,
        hh=hh,
        acc=acc,
        amount=Decimal("-10.00"),
        when=now - timedelta(days=4),
        merchant="Ambrosia",
    )
    credit = _tx(
        user=user,
        hh=hh,
        acc=acc,
        amount=Decimal("10.00"),
        when=now - timedelta(days=1),
        merchant="Statement Credit",
    )
    db.add_all([charge, credit])
    await db.flush()
    await emit_credit_suggestions_for_household(db, hh.id)

    res = await db.execute(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.type == NOTIFICATION_TYPE,
        )
    )
    notif = res.scalar_one()

    _override_user(app, user, db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(f"/transactions/credit-suggestions/{notif.id}/dismiss")
    assert r.status_code == 200
    await db.refresh(notif)
    assert notif.status == "dismissed"


@pytest.mark.asyncio
async def test_list_endpoint_returns_pending_only(app, db):
    user, hh, acc = await _seed(db)
    now = datetime.now(timezone.utc)
    charge = _tx(
        user=user,
        hh=hh,
        acc=acc,
        amount=Decimal("-7.50"),
        when=now - timedelta(days=2),
        merchant="Ambrosia",
    )
    credit = _tx(
        user=user,
        hh=hh,
        acc=acc,
        amount=Decimal("7.50"),
        when=now - timedelta(days=1),
        merchant="Statement Credit",
    )
    db.add_all([charge, credit])
    await db.flush()
    await emit_credit_suggestions_for_household(db, hh.id)

    _override_user(app, user, db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/transactions/credit-suggestions")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    item = items[0]
    assert item["amount"] == 7.5
    assert item["merchant_credit_name"] == "Statement Credit"
    assert item["merchant_counterpart_name"] == "Ambrosia"
