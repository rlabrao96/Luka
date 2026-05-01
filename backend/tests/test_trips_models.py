import pytest
from sqlalchemy import select

from modules.trips.models import Trip, TripAttendee


@pytest.mark.asyncio
async def test_can_insert_and_query_trip(db, make_trip):
    trip = await make_trip(name="Test Trip", base_currency="USD")

    fetched = (await db.execute(select(Trip).where(Trip.id == trip.id))).scalar_one()
    assert fetched.name == "Test Trip"
    assert fetched.base_currency == "USD"
    assert fetched.status == "active"


@pytest.mark.asyncio
async def test_can_insert_attendee(db, make_trip, make_attendee):
    trip = await make_trip(name="T")
    a = await make_attendee(trip, display_name="External Friend")

    fetched = (await db.execute(select(TripAttendee).where(TripAttendee.id == a.id))).scalar_one()
    assert fetched.user_id is None
    assert fetched.display_name == "External Friend"
    assert fetched.left_at is None
