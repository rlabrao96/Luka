import uuid
from datetime import date

import pytest
from sqlalchemy import select

from modules.auth.models import User
from modules.trips.models import Trip, TripAttendee


@pytest.mark.asyncio
async def test_can_insert_and_query_trip(db):
    user = User(
        id=uuid.uuid4(),
        email=f"creator_{uuid.uuid4().hex[:8]}@test.cl",
        full_name="Creator",
        email_provider="gmail",
        whatsapp_verified=False,
    )
    db.add(user)
    await db.flush()

    trip = Trip(
        creator_user_id=user.id,
        name="Test Trip",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 7),
        base_currency="USD",
    )
    db.add(trip)
    await db.flush()

    fetched = (await db.execute(select(Trip).where(Trip.id == trip.id))).scalar_one()
    assert fetched.name == "Test Trip"
    assert fetched.base_currency == "USD"
    assert fetched.status == "active"


@pytest.mark.asyncio
async def test_can_insert_attendee(db):
    user = User(
        id=uuid.uuid4(),
        email=f"u_{uuid.uuid4().hex[:8]}@test.cl",
        full_name="U",
        email_provider="gmail",
        whatsapp_verified=False,
    )
    db.add(user)
    await db.flush()
    trip = Trip(
        creator_user_id=user.id,
        name="T",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 7),
        base_currency="USD",
    )
    db.add(trip)
    await db.flush()
    a = TripAttendee(trip_id=trip.id, user_id=user.id, display_name="U")
    db.add(a)
    await db.flush()
    fetched = (await db.execute(select(TripAttendee).where(TripAttendee.id == a.id))).scalar_one()
    assert fetched.display_name == "U"
    assert fetched.left_at is None
