"""Router tests for the Trips (Viajes) module — Phase 2 (Tasks 2.5 + 2.6).

Covers GET/POST/GET-by-id/PATCH/DELETE on /trips, plus POST/DELETE on
/trips/{id}/attendees. Authentication is overridden via
``app.dependency_overrides`` and the DB session is the per-test SAVEPOINT
``db`` fixture from ``conftest.py``.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from modules.auth.models import User
from modules.trips import service as trips_service
from modules.trips.schemas import CreateAttendeeInput


def _override(app, user: User, db):
    from core.database import get_db
    from core.security import get_current_user

    async def _fake_db():
        yield db

    async def _fake_user():
        return user

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _fake_user


async def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# GET /trips
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_trips_returns_buckets(app, db, make_user, make_trip):
    user = await make_user()
    today = date.today()
    await make_trip(
        creator=user,
        start_date=today - timedelta(days=1),
        end_date=today + timedelta(days=2),
    )
    _override(app, user, db)
    async with await _client(app) as c:
        r = await c.get("/trips")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"active", "upcoming", "past"}
    assert len(body["active"]) == 1


@pytest.mark.asyncio
async def test_list_trips_403_when_flag_off(app, db, make_user):
    user = await make_user(feature_trips_enabled=False)
    _override(app, user, db)
    async with await _client(app) as c:
        r = await c.get("/trips")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# POST /trips
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_trip_201(app, db, make_user):
    user = await make_user()
    _override(app, user, db)
    payload = {
        "name": "Cartagena",
        "start_date": "2026-05-01",
        "end_date": "2026-05-07",
        "base_currency": "USD",
        "attendees": [],
    }
    async with await _client(app) as c:
        r = await c.post("/trips", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "Cartagena"
    assert body["base_currency"] == "USD"
    assert "your_net_balance" in body


@pytest.mark.asyncio
async def test_create_trip_invalid_dates_422(app, db, make_user):
    user = await make_user()
    _override(app, user, db)
    payload = {
        "name": "Bad",
        "start_date": "2026-05-10",
        "end_date": "2026-05-01",
        "base_currency": "USD",
    }
    async with await _client(app) as c:
        r = await c.post("/trips", json=payload)
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /trips/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_trip_returns_detail(app, db, make_user, make_trip, make_attendee):
    user = await make_user()
    trip = await make_trip(creator=user)
    await make_attendee(trip, display_name="External Friend")
    _override(app, user, db)
    async with await _client(app) as c:
        r = await c.get(f"/trips/{trip.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == str(trip.id)
    assert len(body["attendees"]) == 2
    # Phase 4 fields exist (empty for Phase 2)
    assert body["balances"] == []
    assert body["settle_suggestions"] == []
    assert body["settlements"] == []


@pytest.mark.asyncio
async def test_get_trip_404_for_non_member(app, db, make_user, make_trip):
    creator = await make_user()
    intruder = await make_user()
    trip = await make_trip(creator=creator)
    _override(app, intruder, db)
    async with await _client(app) as c:
        r = await c.get(f"/trips/{trip.id}")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /trips/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_trip_renames(app, db, make_user, make_trip):
    user = await make_user()
    trip = await make_trip(creator=user)
    _override(app, user, db)
    async with await _client(app) as c:
        r = await c.patch(f"/trips/{trip.id}", json={"name": "Renamed"})
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"


@pytest.mark.asyncio
async def test_patch_trip_403_for_non_creator(app, db, make_user, make_trip):
    creator = await make_user()
    other = await make_user()
    trip = await make_trip(creator=creator)
    await trips_service.add_attendee(db, trip, creator, CreateAttendeeInput(email=other.email))
    _override(app, other, db)
    async with await _client(app) as c:
        r = await c.patch(f"/trips/{trip.id}", json={"name": "Nope"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_patch_trip_base_currency_400(app, db, make_user, make_trip):
    user = await make_user()
    trip = await make_trip(creator=user)
    _override(app, user, db)
    async with await _client(app) as c:
        r = await c.patch(f"/trips/{trip.id}", json={"base_currency": "EUR"})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /trips/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_trip_204(app, db, make_user, make_trip):
    user = await make_user()
    trip = await make_trip(creator=user)
    _override(app, user, db)
    async with await _client(app) as c:
        r = await c.delete(f"/trips/{trip.id}")
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_trip_403_for_non_creator(app, db, make_user, make_trip):
    creator = await make_user()
    other = await make_user()
    trip = await make_trip(creator=creator)
    await trips_service.add_attendee(db, trip, creator, CreateAttendeeInput(email=other.email))
    _override(app, other, db)
    async with await _client(app) as c:
        r = await c.delete(f"/trips/{trip.id}")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# POST /trips/{id}/attendees
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_attendee_by_email_201(app, db, make_user, make_trip):
    creator = await make_user()
    other = await make_user(email="invitee@test.cl", full_name="Invitee")
    trip = await make_trip(creator=creator)
    _override(app, creator, db)
    async with await _client(app) as c:
        r = await c.post(f"/trips/{trip.id}/attendees", json={"email": "invitee@test.cl"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user_id"] == str(other.id)


@pytest.mark.asyncio
async def test_add_external_attendee_by_display_name_201(app, db, make_user, make_trip):
    user = await make_user()
    trip = await make_trip(creator=user)
    _override(app, user, db)
    async with await _client(app) as c:
        r = await c.post(f"/trips/{trip.id}/attendees", json={"display_name": "Pedro"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user_id"] is None
    assert body["display_name"] == "Pedro"


@pytest.mark.asyncio
async def test_add_attendee_duplicate_409(app, db, make_user, make_trip):
    creator = await make_user()
    await make_user(email="dup@test.cl")
    trip = await make_trip(creator=creator)
    _override(app, creator, db)
    async with await _client(app) as c:
        r1 = await c.post(f"/trips/{trip.id}/attendees", json={"email": "dup@test.cl"})
        assert r1.status_code == 201
        r2 = await c.post(f"/trips/{trip.id}/attendees", json={"email": "dup@test.cl"})
    assert r2.status_code == 409


# ---------------------------------------------------------------------------
# DELETE /trips/{id}/attendees/{aid}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_self_leave_204(app, db, make_user, make_trip):
    creator = await make_user()
    other = await make_user()
    trip = await make_trip(creator=creator)
    other_attendee = await trips_service.add_attendee(
        db, trip, creator, CreateAttendeeInput(email=other.email)
    )
    _override(app, other, db)
    async with await _client(app) as c:
        r = await c.delete(f"/trips/{trip.id}/attendees/{other_attendee.id}")
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_non_creator_cannot_remove_third_party_403(app, db, make_user, make_trip):
    creator = await make_user()
    other = await make_user()
    third = await make_user()
    trip = await make_trip(creator=creator)
    await trips_service.add_attendee(db, trip, creator, CreateAttendeeInput(email=other.email))
    third_attendee = await trips_service.add_attendee(
        db, trip, creator, CreateAttendeeInput(email=third.email)
    )
    _override(app, other, db)
    async with await _client(app) as c:
        r = await c.delete(f"/trips/{trip.id}/attendees/{third_attendee.id}")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_attendees_endpoint_403_when_flag_off(app, db, make_user, make_trip):
    user = await make_user()
    trip = await make_trip(creator=user)
    user.feature_trips_enabled = False
    await db.flush()
    _override(app, user, db)
    async with await _client(app) as c:
        r = await c.post(f"/trips/{trip.id}/attendees", json={"display_name": "Pedro"})
    assert r.status_code == 403
