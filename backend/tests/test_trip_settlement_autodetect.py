"""Tests for trip settlement auto-detect — Phase 6 Tasks 6.2 + 6.3.

Spec ``docs/superpowers/specs/2026-04-30-viajes-trips-design.md`` §4.7.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from core.database import get_db
from core.security import get_current_user

# Ensure SQLAlchemy can resolve trip_expenses.transaction_id → transactions.id FK.
from modules.transactions import models as _txn_models  # noqa: F401
from modules.trips import service as trips_service
from modules.trips.auto_detect import try_match_settlement
from modules.trips.models import (
    TripSettlement,
    TripSettlementDismissal,
)
from modules.trips.schemas import (
    CreateAttendeeInput,
    CreateExpenseRequest,
    SplitInput,
)


def _override(app, user, db):
    async def _u():
        return user

    async def _d():
        yield db

    app.dependency_overrides[get_current_user] = _u
    app.dependency_overrides[get_db] = _d


async def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _make_household(db):
    from modules.households.models import Household

    h = Household(id=uuid.uuid4(), name="H", type="individual")
    db.add(h)
    await db.flush()
    return h


async def _make_transaction(
    db,
    user,
    household,
    *,
    amount=Decimal("-80.00"),
    currency="USD",
    transaction_date=None,
    transaction_type="expense",
    raw_merchant="JOHN DOE ZELLE",
):
    from modules.transactions.models import Transaction

    if transaction_date is None:
        transaction_date = datetime(2026, 5, 8, tzinfo=timezone.utc)
    txn = Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=household.id,
        bank_account_id=None,
        raw_merchant_name=raw_merchant,
        amount=amount,
        currency=currency,
        transaction_date=transaction_date,
        source="plaid",
        source_type="plaid",
        status="settled",
        transaction_type=transaction_type,
    )
    db.add(txn)
    await db.flush()
    return txn


async def _seed_debt(
    db, trip, payer_attendee, debtor_user, debtor_attendee, amount=Decimal("160.00")
):
    """Make ``debtor`` owe ``payer`` $80 by recording an expense paid 100% by
    payer with an even split between payer and debtor."""
    half = amount / 2
    # Use the trip creator's user (passed as `payer_user` via `trip.creator_user`).
    payer_user = trip.creator_user
    await trips_service.create_expense(
        db,
        trip,
        payer_user,
        CreateExpenseRequest(
            payer_attendee_id=payer_attendee.id,
            description="Hotel",
            amount=amount,
            currency=trip.base_currency,
            expense_date=trip.start_date,
            splits=[
                SplitInput(
                    attendee_id=payer_attendee.id,
                    share_type="custom_amount",
                    share_amount=half,
                ),
                SplitInput(
                    attendee_id=debtor_attendee.id,
                    share_type="custom_amount",
                    share_amount=half,
                ),
            ],
        ),
    )
    await db.flush()


@pytest.mark.asyncio
async def test_zelle_to_attendee_within_window_emits_notification(app, db, make_user, make_trip):
    payer = await make_user(full_name="Jane Payer")
    debtor = await make_user(email=f"debtor_{uuid.uuid4().hex[:6]}@test.cl", full_name="John Doe")
    h = await _make_household(db)
    trip = await make_trip(
        creator=payer,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 7),
        base_currency="USD",
    )
    debtor_a = await trips_service.add_attendee(
        db, trip, payer, CreateAttendeeInput(email=debtor.email)
    )
    await _seed_debt(db, trip, trip.creator_attendee, debtor, debtor_a)

    # Debtor's outflow $80 to John Doe — but actually debtor IS John Doe.
    # Reframe: debtor (John Doe) sends $80 to payer (Jane Payer). The
    # transaction belongs to debtor (user=debtor) with the merchant being
    # payer's name.
    txn = await _make_transaction(
        db,
        debtor,
        h,
        amount=Decimal("-80.00"),
        currency="USD",
        raw_merchant="JANE PAYER ZELLE",
        transaction_date=datetime(2026, 5, 8, tzinfo=timezone.utc),
    )

    notifs = await try_match_settlement(db, txn)
    assert len(notifs) == 1


@pytest.mark.asyncio
async def test_amount_outside_tolerance_no_notification(app, db, make_user, make_trip):
    payer = await make_user(full_name="Jane Payer")
    debtor = await make_user(email=f"debtor_{uuid.uuid4().hex[:6]}@test.cl", full_name="John Doe")
    h = await _make_household(db)
    trip = await make_trip(creator=payer, start_date=date(2026, 5, 1), end_date=date(2026, 5, 7))
    debtor_a = await trips_service.add_attendee(
        db, trip, payer, CreateAttendeeInput(email=debtor.email)
    )
    await _seed_debt(db, trip, trip.creator_attendee, debtor, debtor_a)

    # $200 — outside both 5% and $5.
    txn = await _make_transaction(
        db,
        debtor,
        h,
        amount=Decimal("-200.00"),
        raw_merchant="JANE PAYER ZELLE",
    )
    notifs = await try_match_settlement(db, txn)
    assert notifs == []


@pytest.mark.asyncio
async def test_within_5pct_emits_notification(app, db, make_user, make_trip):
    payer = await make_user(full_name="Jane Payer")
    debtor = await make_user(email=f"debtor_{uuid.uuid4().hex[:6]}@test.cl", full_name="John Doe")
    h = await _make_household(db)
    trip = await make_trip(creator=payer, start_date=date(2026, 5, 1), end_date=date(2026, 5, 7))
    debtor_a = await trips_service.add_attendee(
        db, trip, payer, CreateAttendeeInput(email=debtor.email)
    )
    # Outstanding $80 → 5% = $4 (< $5 floor) → tolerance is $4.
    await _seed_debt(db, trip, trip.creator_attendee, debtor, debtor_a)

    # $84 — exactly at the 5% boundary; must match.
    txn = await _make_transaction(
        db, debtor, h, amount=Decimal("-84.00"), raw_merchant="JANE PAYER"
    )
    notifs = await try_match_settlement(db, txn)
    assert len(notifs) == 1


@pytest.mark.asyncio
async def test_above_tolerance_no_match(app, db, make_user, make_trip):
    payer = await make_user(full_name="Jane Payer")
    debtor = await make_user(email=f"debtor_{uuid.uuid4().hex[:6]}@test.cl", full_name="John Doe")
    h = await _make_household(db)
    trip = await make_trip(creator=payer, start_date=date(2026, 5, 1), end_date=date(2026, 5, 7))
    debtor_a = await trips_service.add_attendee(
        db, trip, payer, CreateAttendeeInput(email=debtor.email)
    )
    await _seed_debt(db, trip, trip.creator_attendee, debtor, debtor_a)

    # Outstanding=$80, $90 deviation = $10 > min(5%=$4, $5=$5) → no match.
    txn = await _make_transaction(
        db, debtor, h, amount=Decimal("-90.00"), raw_merchant="JANE PAYER"
    )
    notifs = await try_match_settlement(db, txn)
    assert notifs == []


@pytest.mark.asyncio
async def test_external_attendee_never_matched(app, db, make_user, make_trip):
    """If only attendees are external (no user_id), name-match never fires."""
    payer = await make_user(full_name="Jane Payer")
    await _make_household(db)
    trip = await make_trip(creator=payer, start_date=date(2026, 5, 1), end_date=date(2026, 5, 7))
    # Add external attendee (display_name only, no user_id).
    ext_a = await trips_service.add_attendee(
        db, trip, payer, CreateAttendeeInput(display_name="John Doe")
    )
    # Seed debt: payer paid full, ext_a owes half.
    await trips_service.create_expense(
        db,
        trip,
        payer,
        CreateExpenseRequest(
            payer_attendee_id=trip.creator_attendee.id,
            description="Hotel",
            amount=Decimal("160.00"),
            currency=trip.base_currency,
            expense_date=trip.start_date,
            splits=[
                SplitInput(
                    attendee_id=trip.creator_attendee.id,
                    share_type="custom_amount",
                    share_amount=Decimal("80.00"),
                ),
                SplitInput(
                    attendee_id=ext_a.id,
                    share_type="custom_amount",
                    share_amount=Decimal("80.00"),
                ),
            ],
        ),
    )
    await db.flush()

    # Only attendees with user_id are eligible — payer's own transaction
    # cannot match an external attendee.
    txn = await _make_transaction(
        db,
        payer,
        await _make_household(db),
        amount=Decimal("80.00"),
        transaction_type="income",
        raw_merchant="JOHN DOE",
    )
    notifs = await try_match_settlement(db, txn)
    assert notifs == []


@pytest.mark.asyncio
async def test_outside_date_window_no_match(app, db, make_user, make_trip):
    payer = await make_user(full_name="Jane Payer")
    debtor = await make_user(email=f"debtor_{uuid.uuid4().hex[:6]}@test.cl", full_name="John Doe")
    h = await _make_household(db)
    trip = await make_trip(creator=payer, start_date=date(2026, 5, 1), end_date=date(2026, 5, 7))
    debtor_a = await trips_service.add_attendee(
        db, trip, payer, CreateAttendeeInput(email=debtor.email)
    )
    await _seed_debt(db, trip, trip.creator_attendee, debtor, debtor_a)

    # 31 days after end_date = 2026-06-07 → outside window (2026-06-06 = end+30).
    far_future = datetime(2026, 6, 8, tzinfo=timezone.utc)
    txn = await _make_transaction(
        db,
        debtor,
        h,
        amount=Decimal("-80.00"),
        raw_merchant="JANE PAYER",
        transaction_date=far_future,
    )
    notifs = await try_match_settlement(db, txn)
    assert notifs == []


@pytest.mark.asyncio
async def test_dismissed_transaction_suppressed(app, db, make_user, make_trip):
    payer = await make_user(full_name="Jane Payer")
    debtor = await make_user(email=f"debtor_{uuid.uuid4().hex[:6]}@test.cl", full_name="John Doe")
    h = await _make_household(db)
    trip = await make_trip(creator=payer, start_date=date(2026, 5, 1), end_date=date(2026, 5, 7))
    debtor_a = await trips_service.add_attendee(
        db, trip, payer, CreateAttendeeInput(email=debtor.email)
    )
    await _seed_debt(db, trip, trip.creator_attendee, debtor, debtor_a)

    txn = await _make_transaction(
        db, debtor, h, amount=Decimal("-80.00"), raw_merchant="JANE PAYER"
    )
    db.add(TripSettlementDismissal(user_id=debtor.id, transaction_id=txn.id))
    await db.flush()

    notifs = await try_match_settlement(db, txn)
    assert notifs == []


@pytest.mark.asyncio
async def test_transfer_type_no_match(app, db, make_user, make_trip):
    payer = await make_user(full_name="Jane Payer")
    debtor = await make_user(email=f"debtor_{uuid.uuid4().hex[:6]}@test.cl", full_name="John Doe")
    h = await _make_household(db)
    trip = await make_trip(creator=payer, start_date=date(2026, 5, 1), end_date=date(2026, 5, 7))
    debtor_a = await trips_service.add_attendee(
        db, trip, payer, CreateAttendeeInput(email=debtor.email)
    )
    await _seed_debt(db, trip, trip.creator_attendee, debtor, debtor_a)

    txn = await _make_transaction(
        db,
        debtor,
        h,
        amount=Decimal("-80.00"),
        raw_merchant="JANE PAYER",
        transaction_type="transfer",
    )
    notifs = await try_match_settlement(db, txn)
    assert notifs == []


@pytest.mark.asyncio
async def test_confirm_endpoint_creates_settlement(app, db, make_user, make_trip):
    payer = await make_user(full_name="Jane Payer")
    debtor = await make_user(email=f"debtor_{uuid.uuid4().hex[:6]}@test.cl", full_name="John Doe")
    h = await _make_household(db)
    trip = await make_trip(creator=payer, start_date=date(2026, 5, 1), end_date=date(2026, 5, 7))
    debtor_a = await trips_service.add_attendee(
        db, trip, payer, CreateAttendeeInput(email=debtor.email)
    )
    await _seed_debt(db, trip, trip.creator_attendee, debtor, debtor_a)
    txn = await _make_transaction(
        db, debtor, h, amount=Decimal("-80.00"), raw_merchant="JANE PAYER"
    )

    _override(app, debtor, db)
    async with await _client(app) as c:
        r = await c.post(
            "/trips/settlement-suggestions/confirm",
            json={
                "trip_id": str(trip.id),
                "from_attendee_id": str(debtor_a.id),
                "to_attendee_id": str(trip.creator_attendee.id),
                "amount": "80.00",
                "currency": "USD",
                "transaction_id": str(txn.id),
            },
        )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["transaction_id"] == str(txn.id)

    # Verify the row landed.
    row = (
        await db.execute(select(TripSettlement).where(TripSettlement.id == uuid.UUID(body["id"])))
    ).scalar_one_or_none()
    assert row is not None
    assert row.transaction_id == txn.id


@pytest.mark.asyncio
async def test_dismiss_endpoint_inserts_dismissal(app, db, make_user, make_trip):
    debtor = await make_user(full_name="John Doe")
    h = await _make_household(db)
    txn = await _make_transaction(db, debtor, h)

    _override(app, debtor, db)
    async with await _client(app) as c:
        r = await c.post(
            "/trips/settlement-suggestions/dismiss",
            json={"transaction_id": str(txn.id)},
        )
    assert r.status_code == 204

    row = (
        await db.execute(
            select(TripSettlementDismissal).where(
                TripSettlementDismissal.user_id == debtor.id,
                TripSettlementDismissal.transaction_id == txn.id,
            )
        )
    ).scalar_one_or_none()
    assert row is not None
