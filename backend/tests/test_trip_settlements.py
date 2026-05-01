"""Tests for the settlement endpoint + balance/suggestion surfacing.

Phase 4 v1: ``POST /trips/{id}/settlements``, ``GET /trips/{id}`` now
includes ``balances`` + ``settle_suggestions``, and ``GET /trips`` returns
real ``your_net_balance`` per trip.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from core.database import get_db
from core.security import get_current_user

# Ensure SQLAlchemy can resolve trip_expenses.transaction_id → transactions.id FK.
from modules.transactions import models as _txn_models  # noqa: F401
from modules.trips import service as trips_service
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
async def test_create_settlement_endpoint_201(app, db, make_user, make_trip):
    creator = await make_user()
    other = await make_user(email="o_set1@example.com")
    trip = await make_trip(creator=creator)
    other_a = await trips_service.add_attendee(
        db, trip, creator, CreateAttendeeInput(email=other.email)
    )

    _override(app, creator, db)
    async with await _client(app) as c:
        r = await c.post(
            f"/trips/{trip.id}/settlements",
            json={
                "from_attendee_id": str(other_a.id),
                "to_attendee_id": str(trip.creator_attendee.id),
                "amount": "30.00",
                "currency": trip.base_currency,
            },
        )
    assert r.status_code == 201, r.text
    body = r.json()
    assert Decimal(body["amount"]) == Decimal("30.00")
    assert body["write_off"] is False


@pytest.mark.asyncio
async def test_create_settlement_currency_mismatch_422(app, db, make_user, make_trip):
    creator = await make_user()
    other = await make_user(email="o_set2@example.com")
    trip = await make_trip(creator=creator, base_currency="USD")
    other_a = await trips_service.add_attendee(
        db, trip, creator, CreateAttendeeInput(email=other.email)
    )

    _override(app, creator, db)
    async with await _client(app) as c:
        r = await c.post(
            f"/trips/{trip.id}/settlements",
            json={
                "from_attendee_id": str(other_a.id),
                "to_attendee_id": str(trip.creator_attendee.id),
                "amount": "30.00",
                "currency": "MXN",
            },
        )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_get_trip_includes_balances_and_suggestions(app, db, make_user, make_trip):
    creator = await make_user()
    other = await make_user(email="o_set3@example.com")
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
            amount=Decimal("100.00"),
            currency=trip.base_currency,
            expense_date=date(2026, 5, 2),
            splits=[
                SplitInput(attendee_id=trip.creator_attendee.id, share_type="equal"),
                SplitInput(attendee_id=other_a.id, share_type="equal"),
            ],
        ),
    )

    _override(app, creator, db)
    async with await _client(app) as c:
        r = await c.get(f"/trips/{trip.id}")
    assert r.status_code == 200
    body = r.json()
    assert len(body["balances"]) == 2
    nets = {b["attendee_id"]: b["net_in_base"] for b in body["balances"]}
    assert Decimal(nets[str(trip.creator_attendee.id)]) == Decimal("50")
    assert Decimal(nets[str(other_a.id)]) == Decimal("-50")
    assert len(body["settle_suggestions"]) == 1
    assert Decimal(body["settle_suggestions"][0]["amount"]) == Decimal("50")


@pytest.mark.asyncio
async def test_list_trips_returns_real_your_net_balance(app, db, make_user, make_trip):
    creator = await make_user()
    other = await make_user(email="o_set4@example.com")
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
            amount=Decimal("100.00"),
            currency=trip.base_currency,
            expense_date=date(2026, 5, 2),
            splits=[
                SplitInput(attendee_id=trip.creator_attendee.id, share_type="equal"),
                SplitInput(attendee_id=other_a.id, share_type="equal"),
            ],
        ),
    )

    _override(app, creator, db)
    async with await _client(app) as c:
        r = await c.get("/trips")
    assert r.status_code == 200
    body = r.json()
    flat = body["active"] + body["upcoming"] + body["past"]
    target = next(t for t in flat if t["id"] == str(trip.id))
    assert Decimal(target["your_net_balance"]) == Decimal("50")
