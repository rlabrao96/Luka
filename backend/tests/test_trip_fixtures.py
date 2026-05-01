import pytest


@pytest.mark.asyncio
async def test_make_user_persists(db, make_user):
    user = await make_user()
    assert user.id is not None
    assert user.feature_trips_enabled is True


@pytest.mark.asyncio
async def test_make_trip_with_creator_attendee(db, make_trip):
    trip = await make_trip()
    assert trip.id is not None
    assert trip.creator_attendee.user_id == trip.creator_user_id


@pytest.mark.asyncio
async def test_make_attendee_external(db, make_trip, make_attendee):
    trip = await make_trip()
    a = await make_attendee(trip, display_name="External")
    assert a.user_id is None
    assert a.display_name == "External"
