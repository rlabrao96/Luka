"""Router + service tests for the Trips invite-link feature (Phase 5).

Covers:
- POST /trips/{id}/invite-link (generate + rotate)
- DELETE /trips/{id}/invite-link (revoke)
- POST /trips/join/{token} (idempotent + sliding-window refresh)
- GET  /trips/preview/{token} (read-only preview)

Auth is overridden via ``app.dependency_overrides`` and the DB session is
the per-test SAVEPOINT ``db`` fixture from ``conftest.py``. We use the same
``_override`` / ``_client`` helper pattern as ``test_trips_router.py``.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from modules.auth.models import User
from modules.trips.models import Trip, TripAttendee


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
# Generate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_invite_link_returns_token_and_url(app, db, make_user, make_trip):
    user = await make_user()
    trip = await make_trip(creator=user)
    _override(app, user, db)
    async with await _client(app) as c:
        r = await c.post(f"/trips/{trip.id}/invite-link")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token"]
    assert "/viajes/join/" in body["url"]
    assert body["url"].endswith(body["token"])
    assert body["expires_at"]


@pytest.mark.asyncio
async def test_invite_link_token_stored_as_sha256(app, db, make_user, make_trip):
    user = await make_user()
    trip = await make_trip(creator=user)
    _override(app, user, db)
    async with await _client(app) as c:
        r = await c.post(f"/trips/{trip.id}/invite-link")
    raw_token = r.json()["token"]
    expected_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    fresh = (await db.execute(select(Trip).where(Trip.id == trip.id))).scalar_one()
    assert fresh.invite_token_hash == expected_hash
    # Raw token must NOT appear anywhere on the row.
    assert raw_token not in (fresh.invite_token_hash or "")


@pytest.mark.asyncio
async def test_generate_invite_link_creator_only_403(app, db, make_user, make_trip, make_attendee):
    creator = await make_user()
    other = await make_user()
    trip = await make_trip(creator=creator)
    await make_attendee(trip, user=other)
    _override(app, other, db)
    async with await _client(app) as c:
        r = await c.post(f"/trips/{trip.id}/invite-link")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_rotate_invite_link_invalidates_old(app, db, make_user, make_trip):
    creator = await make_user()
    joiner = await make_user()
    trip = await make_trip(creator=creator)
    _override(app, creator, db)
    async with await _client(app) as c:
        r1 = await c.post(f"/trips/{trip.id}/invite-link")
        token1 = r1.json()["token"]
        r2 = await c.post(f"/trips/{trip.id}/invite-link")
        token2 = r2.json()["token"]
    assert token1 != token2

    # Joiner attempts to redeem the old one → 404, new one → 200.
    _override(app, joiner, db)
    async with await _client(app) as c:
        r_old = await c.post(f"/trips/join/{token1}")
        r_new = await c.post(f"/trips/join/{token2}")
    assert r_old.status_code == 404
    assert r_new.status_code == 200


# ---------------------------------------------------------------------------
# Revoke
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revoke_invite_link_204(app, db, make_user, make_trip):
    creator = await make_user()
    joiner = await make_user()
    trip = await make_trip(creator=creator)
    _override(app, creator, db)
    async with await _client(app) as c:
        gen = await c.post(f"/trips/{trip.id}/invite-link")
        token = gen.json()["token"]
        rev = await c.delete(f"/trips/{trip.id}/invite-link")
    assert rev.status_code == 204

    _override(app, joiner, db)
    async with await _client(app) as c:
        r = await c.post(f"/trips/join/{token}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_revoke_invite_link_creator_only(app, db, make_user, make_trip, make_attendee):
    creator = await make_user()
    other = await make_user()
    trip = await make_trip(creator=creator)
    await make_attendee(trip, user=other)
    _override(app, other, db)
    async with await _client(app) as c:
        r = await c.delete(f"/trips/{trip.id}/invite-link")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Join
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_join_via_token_adds_attendee(app, db, make_user, make_trip):
    creator = await make_user()
    joiner = await make_user(full_name="Newcomer")
    trip = await make_trip(creator=creator)
    _override(app, creator, db)
    async with await _client(app) as c:
        gen = await c.post(f"/trips/{trip.id}/invite-link")
    token = gen.json()["token"]

    _override(app, joiner, db)
    async with await _client(app) as c:
        r = await c.post(f"/trips/join/{token}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == str(trip.id)

    rows = (
        (
            await db.execute(
                select(TripAttendee).where(
                    TripAttendee.trip_id == trip.id,
                    TripAttendee.user_id == joiner.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].display_name == "Newcomer"
    assert rows[0].left_at is None


@pytest.mark.asyncio
async def test_join_idempotent_for_existing_attendee(app, db, make_user, make_trip):
    creator = await make_user()
    joiner = await make_user()
    trip = await make_trip(creator=creator)
    _override(app, creator, db)
    async with await _client(app) as c:
        gen = await c.post(f"/trips/{trip.id}/invite-link")
    token = gen.json()["token"]

    _override(app, joiner, db)
    async with await _client(app) as c:
        r1 = await c.post(f"/trips/join/{token}")
        r2 = await c.post(f"/trips/join/{token}")
    assert r1.status_code == 200
    assert r2.status_code == 200

    rows = (
        (
            await db.execute(
                select(TripAttendee).where(
                    TripAttendee.trip_id == trip.id,
                    TripAttendee.user_id == joiner.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_join_re_adds_left_attendee(app, db, make_user, make_trip, make_attendee):
    creator = await make_user()
    joiner = await make_user()
    trip = await make_trip(creator=creator)
    attendee = await make_attendee(trip, user=joiner)
    # Mark them as left.
    attendee.left_at = datetime.now(timezone.utc)
    await db.flush()

    _override(app, creator, db)
    async with await _client(app) as c:
        gen = await c.post(f"/trips/{trip.id}/invite-link")
    token = gen.json()["token"]

    _override(app, joiner, db)
    async with await _client(app) as c:
        r = await c.post(f"/trips/join/{token}")
    assert r.status_code == 200

    rows = (
        (
            await db.execute(
                select(TripAttendee).where(
                    TripAttendee.trip_id == trip.id,
                    TripAttendee.user_id == joiner.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].left_at is None


@pytest.mark.asyncio
async def test_join_expired_token_404(app, db, make_user, make_trip):
    creator = await make_user()
    joiner = await make_user()
    trip = await make_trip(creator=creator)
    _override(app, creator, db)
    async with await _client(app) as c:
        gen = await c.post(f"/trips/{trip.id}/invite-link")
    token = gen.json()["token"]

    # Manually expire it.
    fresh = (await db.execute(select(Trip).where(Trip.id == trip.id))).scalar_one()
    fresh.invite_token_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db.flush()

    _override(app, joiner, db)
    async with await _client(app) as c:
        r = await c.post(f"/trips/join/{token}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_join_invalid_token_404(app, db, make_user):
    joiner = await make_user()
    _override(app, joiner, db)
    async with await _client(app) as c:
        r = await c.post(
            "/trips/join/this-is-not-a-real-token-abcdef0123456789"  # pragma: allowlist secret
        )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_join_refreshes_expiry(app, db, make_user, make_trip):
    creator = await make_user()
    joiner = await make_user()
    trip = await make_trip(creator=creator)
    _override(app, creator, db)
    async with await _client(app) as c:
        gen = await c.post(f"/trips/{trip.id}/invite-link")
    token = gen.json()["token"]

    initial = (
        (await db.execute(select(Trip).where(Trip.id == trip.id)))
        .scalar_one()
        .invite_token_expires_at
    )

    # Force a measurable gap so the refresh value is strictly larger.
    await asyncio.sleep(0.05)

    _override(app, joiner, db)
    async with await _client(app) as c:
        r = await c.post(f"/trips/join/{token}")
    assert r.status_code == 200

    refreshed = (
        (await db.execute(select(Trip).where(Trip.id == trip.id)))
        .scalar_one()
        .invite_token_expires_at
    )
    assert refreshed > initial


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_token_returns_trip_metadata(app, db, make_user, make_trip, make_attendee):
    creator = await make_user()
    other = await make_user()
    trip = await make_trip(creator=creator, name="Patagonia 26")
    await make_attendee(trip, user=other)
    _override(app, creator, db)
    async with await _client(app) as c:
        gen = await c.post(f"/trips/{trip.id}/invite-link")
    token = gen.json()["token"]

    viewer = await make_user()
    _override(app, viewer, db)
    async with await _client(app) as c:
        r = await c.get(f"/trips/preview/{token}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Patagonia 26"
    assert body["base_currency"] == "USD"
    assert body["attendee_count"] == 2  # creator + other
    assert body["start_date"]
    assert body["end_date"]


@pytest.mark.asyncio
async def test_preview_does_not_refresh_expiry(app, db, make_user, make_trip):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    _override(app, creator, db)
    async with await _client(app) as c:
        gen = await c.post(f"/trips/{trip.id}/invite-link")
    token = gen.json()["token"]

    initial = (
        (await db.execute(select(Trip).where(Trip.id == trip.id)))
        .scalar_one()
        .invite_token_expires_at
    )

    viewer = await make_user()
    _override(app, viewer, db)
    async with await _client(app) as c:
        r = await c.get(f"/trips/preview/{token}")
    assert r.status_code == 200

    after = (
        (await db.execute(select(Trip).where(Trip.id == trip.id)))
        .scalar_one()
        .invite_token_expires_at
    )
    assert after == initial


@pytest.mark.asyncio
async def test_preview_invalid_token_404(app, db, make_user):
    viewer = await make_user()
    _override(app, viewer, db)
    async with await _client(app) as c:
        r = await c.get(
            "/trips/preview/garbage-token-xyz-0000000000000000000000"  # pragma: allowlist secret
        )
    assert r.status_code == 404
