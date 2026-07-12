"""Tests for the trips service layer (Phase 2, Task 2.4).

Covers create / list / get / update / archive trip + add / remove attendee.
Phase 4 (balances + base_currency re-anchor) is intentionally out of scope.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from modules.trips import service as trips_service
from modules.trips.models import TripAttendee
from modules.trips.schemas import (
    CreateAttendeeInput,
    CreateTripRequest,
    UpdateTripRequest,
)


def _basic_payload(**overrides) -> CreateTripRequest:
    base = dict(
        name="Test Trip",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 7),
        base_currency="USD",
        attendees=[],
    )
    base.update(overrides)
    return CreateTripRequest(**base)


# --- create_trip ---


@pytest.mark.asyncio
async def test_create_trip_adds_creator_as_attendee(db, make_user):
    user = await make_user()
    trip = await trips_service.create_trip(
        db, creator=user, payload=_basic_payload(name="Cartagena")
    )
    attendees = (
        (await db.execute(select(TripAttendee).where(TripAttendee.trip_id == trip.id)))
        .scalars()
        .all()
    )
    assert len(attendees) == 1
    assert attendees[0].user_id == user.id
    assert trip.creator_user_id == user.id
    assert trip.status == "active"


@pytest.mark.asyncio
async def test_create_trip_with_email_resolves_luka_user(db, make_user):
    creator = await make_user()
    other = await make_user(email="other_resolve@test.cl", full_name="Other")
    trip = await trips_service.create_trip(
        db,
        creator,
        payload=_basic_payload(attendees=[CreateAttendeeInput(email="other_resolve@test.cl")]),
    )
    attendees = (
        (await db.execute(select(TripAttendee).where(TripAttendee.trip_id == trip.id)))
        .scalars()
        .all()
    )
    luka = [a for a in attendees if a.user_id is not None]
    assert {a.user_id for a in luka} == {creator.id, other.id}


@pytest.mark.asyncio
async def test_create_trip_unknown_email_creates_external_stub(db, make_user):
    creator = await make_user()
    trip = await trips_service.create_trip(
        db,
        creator,
        payload=_basic_payload(
            attendees=[CreateAttendeeInput(email="ghost@example.com", display_name="Ghost")]
        ),
    )
    attendees = (
        (await db.execute(select(TripAttendee).where(TripAttendee.trip_id == trip.id)))
        .scalars()
        .all()
    )
    external = [a for a in attendees if a.user_id is None]
    assert len(external) == 1
    assert external[0].display_name == "Ghost"


@pytest.mark.asyncio
async def test_create_trip_external_falls_back_to_email_local_part(db, make_user):
    creator = await make_user()
    trip = await trips_service.create_trip(
        db,
        creator,
        payload=_basic_payload(attendees=[CreateAttendeeInput(email="solo@example.com")]),
    )
    attendees = (
        (await db.execute(select(TripAttendee).where(TripAttendee.trip_id == trip.id)))
        .scalars()
        .all()
    )
    external = [a for a in attendees if a.user_id is None]
    assert len(external) == 1
    assert external[0].display_name == "solo"


# --- list_trips ---


@pytest.mark.asyncio
async def test_list_trips_groups_by_date(db, make_user, make_trip):
    user = await make_user()
    today = date.today()
    active = await make_trip(
        creator=user, start_date=today - timedelta(days=1), end_date=today + timedelta(days=1)
    )
    upcoming = await make_trip(
        creator=user, start_date=today + timedelta(days=10), end_date=today + timedelta(days=15)
    )
    past = await make_trip(
        creator=user, start_date=today - timedelta(days=20), end_date=today - timedelta(days=10)
    )
    result = await trips_service.list_trips(db, user)
    assert {t["id"] for t in result["active"]} == {active.id}
    assert {t["id"] for t in result["upcoming"]} == {upcoming.id}
    assert {t["id"] for t in result["past"]} == {past.id}
    # No expenses seeded — everyone's real net balance is exactly 0.
    for bucket in ("active", "upcoming", "past"):
        for t in result[bucket]:
            assert t["your_net_balance"] == Decimal("0")


@pytest.mark.asyncio
async def test_list_trips_excludes_left_members(db, make_user, make_trip):
    creator = await make_user()
    other = await make_user()
    trip = await make_trip(creator=creator)
    # add `other` then have them leave
    a = await trips_service.add_attendee(db, trip, creator, CreateAttendeeInput(email=other.email))
    await trips_service.remove_attendee(db, trip.id, a.id, other)

    result = await trips_service.list_trips(db, other)
    all_ids = {t["id"] for bucket in result.values() for t in bucket}
    assert trip.id not in all_ids


# --- get_trip ---


@pytest.mark.asyncio
async def test_get_trip_returns_404_for_non_member(db, make_user, make_trip):
    creator = await make_user()
    intruder = await make_user()
    trip = await make_trip(creator=creator)
    with pytest.raises(HTTPException) as ex:
        await trips_service.get_trip(db, trip.id, intruder)
    assert ex.value.status_code == 404


@pytest.mark.asyncio
async def test_get_trip_returns_attendees(db, make_user, make_trip, make_attendee):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    await make_attendee(trip, display_name="External Friend")
    fetched = await trips_service.get_trip(db, trip.id, creator)
    assert len(fetched.attendees) == 2


# --- update_trip ---


@pytest.mark.asyncio
async def test_update_trip_creator_only(db, make_user, make_trip):
    creator = await make_user()
    other = await make_user()
    trip = await make_trip(creator=creator)
    await trips_service.add_attendee(db, trip, creator, CreateAttendeeInput(email=other.email))

    with pytest.raises(HTTPException) as ex:
        await trips_service.update_trip(db, trip.id, other, UpdateTripRequest(name="Renamed"))
    assert ex.value.status_code == 403


@pytest.mark.asyncio
async def test_update_trip_creator_can_rename(db, make_user, make_trip):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    updated = await trips_service.update_trip(
        db, trip.id, creator, UpdateTripRequest(name="New Name")
    )
    assert updated.name == "New Name"


@pytest.mark.asyncio
async def test_update_trip_base_currency_blocked_in_phase_2(db, make_user, make_trip):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    with pytest.raises(HTTPException) as ex:
        await trips_service.update_trip(
            db, trip.id, creator, UpdateTripRequest(base_currency="EUR")
        )
    assert ex.value.status_code == 400
    assert "Phase 4" in ex.value.detail or "phase 4" in ex.value.detail.lower()


# --- archive_trip ---


@pytest.mark.asyncio
async def test_archive_trip_creator_only(db, make_user, make_trip):
    creator = await make_user()
    other = await make_user()
    trip = await make_trip(creator=creator)
    await trips_service.add_attendee(db, trip, creator, CreateAttendeeInput(email=other.email))

    with pytest.raises(HTTPException) as ex:
        await trips_service.archive_trip(db, trip.id, other)
    assert ex.value.status_code == 403

    await trips_service.archive_trip(db, trip.id, creator)
    refreshed = await trips_service.get_trip(db, trip.id, creator)
    assert refreshed.status == "archived"


# --- add_attendee ---


@pytest.mark.asyncio
async def test_add_attendee_duplicate_luka_returns_409(db, make_user, make_trip):
    creator = await make_user()
    await make_user(email="dup@test.cl")
    trip = await make_trip(creator=creator)
    await trips_service.add_attendee(db, trip, creator, CreateAttendeeInput(email="dup@test.cl"))
    with pytest.raises(HTTPException) as ex:
        await trips_service.add_attendee(
            db, trip, creator, CreateAttendeeInput(email="dup@test.cl")
        )
    assert ex.value.status_code == 409


@pytest.mark.asyncio
async def test_add_external_attendee_uses_display_name(db, make_user, make_trip):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    attendee = await trips_service.add_attendee(
        db, trip, creator, CreateAttendeeInput(display_name="Pedro")
    )
    assert attendee.user_id is None
    assert attendee.display_name == "Pedro"


@pytest.mark.asyncio
async def test_add_attendee_requires_active_member(db, make_user, make_trip):
    creator = await make_user()
    intruder = await make_user()
    trip = await make_trip(creator=creator)
    with pytest.raises(HTTPException) as ex:
        await trips_service.add_attendee(
            db, trip, intruder, CreateAttendeeInput(display_name="Random")
        )
    assert ex.value.status_code == 403


# --- remove_attendee ---


@pytest.mark.asyncio
async def test_self_leave_allowed_for_non_creator(db, make_user, make_trip):
    creator = await make_user()
    other = await make_user()
    trip = await make_trip(creator=creator)
    other_attendee = await trips_service.add_attendee(
        db, trip, creator, CreateAttendeeInput(email=other.email)
    )
    await trips_service.remove_attendee(db, trip.id, other_attendee.id, other)
    fetched = (
        await db.execute(select(TripAttendee).where(TripAttendee.id == other_attendee.id))
    ).scalar_one()
    assert fetched.left_at is not None


@pytest.mark.asyncio
async def test_non_creator_cannot_remove_other_attendee(db, make_user, make_trip):
    creator = await make_user()
    other = await make_user()
    third = await make_user()
    trip = await make_trip(creator=creator)
    await trips_service.add_attendee(db, trip, creator, CreateAttendeeInput(email=other.email))
    a_third = await trips_service.add_attendee(
        db, trip, creator, CreateAttendeeInput(email=third.email)
    )
    with pytest.raises(HTTPException) as ex:
        await trips_service.remove_attendee(db, trip.id, a_third.id, other)
    assert ex.value.status_code == 403


@pytest.mark.asyncio
async def test_creator_can_remove_other_attendee(db, make_user, make_trip):
    creator = await make_user()
    other = await make_user()
    trip = await make_trip(creator=creator)
    a = await trips_service.add_attendee(db, trip, creator, CreateAttendeeInput(email=other.email))
    await trips_service.remove_attendee(db, trip.id, a.id, creator)
    fetched = (await db.execute(select(TripAttendee).where(TripAttendee.id == a.id))).scalar_one()
    assert fetched.left_at is not None


@pytest.mark.asyncio
async def test_remove_attendee_not_on_trip_returns_404(db, make_user, make_trip):
    import uuid

    creator = await make_user()
    trip = await make_trip(creator=creator)
    with pytest.raises(HTTPException) as ex:
        await trips_service.remove_attendee(db, trip.id, uuid.uuid4(), creator)
    assert ex.value.status_code == 404
