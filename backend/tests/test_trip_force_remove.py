"""Tests for ``POST /trips/{id}/attendees/{aid}/force-remove`` (Phase 4 Task 4.6).

Creator-only. If the attendee has a non-zero balance, a ``write_off=true``
settlement is inserted to zero them out before ``left_at`` is set.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from core.database import get_db
from core.security import get_current_user

# Ensure SQLAlchemy can resolve trip_expenses.transaction_id → transactions.id FK.
from modules.transactions import models as _txn_models  # noqa: F401
from modules.trips import service as trips_service
from modules.trips.models import TripAttendee, TripSettlement
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


@pytest.mark.asyncio
async def test_force_remove_with_outstanding_balance_creates_writeoff(
    app, db, make_user, make_trip
):
    creator = await make_user()
    other = await make_user(email="fr1@example.com")
    trip = await make_trip(creator=creator)
    other_a = await trips_service.add_attendee(
        db, trip, creator, CreateAttendeeInput(email=other.email)
    )
    await trips_service.create_expense(
        db,
        trip,
        creator,
        CreateExpenseRequest(
            payer_attendee_id=trip.creator_attendee.id,
            description="d",
            amount=Decimal("60.00"),
            currency=trip.base_currency,
            expense_date=date(2026, 5, 2),
            splits=[
                SplitInput(attendee_id=trip.creator_attendee.id, share_type="equal"),
                SplitInput(attendee_id=other_a.id, share_type="equal"),
            ],
        ),
    )
    # other_a now owes $30 (net = -30)

    _override(app, creator, db)
    async with await _client(app) as c:
        r = await c.post(f"/trips/{trip.id}/attendees/{other_a.id}/force-remove")
    assert r.status_code in (200, 204), r.text

    fetched = (
        await db.execute(select(TripAttendee).where(TripAttendee.id == other_a.id))
    ).scalar_one()
    assert fetched.left_at is not None

    settlements = (
        (await db.execute(select(TripSettlement).where(TripSettlement.trip_id == trip.id)))
        .scalars()
        .all()
    )
    assert any(s.write_off for s in settlements)
    # The write-off should zero the attendee's net.
    write_off = next(s for s in settlements if s.write_off)
    assert write_off.amount == Decimal("30.00")
    # Debtor: from creator → to attendee.
    assert write_off.from_attendee_id == trip.creator_attendee.id
    assert write_off.to_attendee_id == other_a.id


@pytest.mark.asyncio
async def test_force_remove_creator_only_403(app, db, make_user, make_trip):
    creator = await make_user()
    other = await make_user(email="fr2@example.com")
    trip = await make_trip(creator=creator)
    other_a = await trips_service.add_attendee(
        db, trip, creator, CreateAttendeeInput(email=other.email)
    )

    _override(app, other, db)
    async with await _client(app) as c:
        r = await c.post(f"/trips/{trip.id}/attendees/{other_a.id}/force-remove")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_force_remove_zero_balance_no_settlement(app, db, make_user, make_trip):
    creator = await make_user()
    other = await make_user(email="fr3@example.com")
    trip = await make_trip(creator=creator)
    other_a = await trips_service.add_attendee(
        db, trip, creator, CreateAttendeeInput(email=other.email)
    )
    # No expenses → balance is 0.

    _override(app, creator, db)
    async with await _client(app) as c:
        r = await c.post(f"/trips/{trip.id}/attendees/{other_a.id}/force-remove")
    assert r.status_code in (200, 204)

    fetched = (
        await db.execute(select(TripAttendee).where(TripAttendee.id == other_a.id))
    ).scalar_one()
    assert fetched.left_at is not None

    settlements = (
        (await db.execute(select(TripSettlement).where(TripSettlement.trip_id == trip.id)))
        .scalars()
        .all()
    )
    assert len(settlements) == 0
