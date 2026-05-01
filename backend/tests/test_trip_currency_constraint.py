"""Phase 4 v1 single-currency cut: expenses must match trip base currency.

See ``docs/superpowers/plans/2026-04-30-viajes-trips.md`` Phase 4 (v1 cut).
Multi-currency + FX is deferred to v2 (see ``FX_INTEGRATION.md``).
"""

from __future__ import annotations

from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient


def _override(app, user, db):
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


@pytest.mark.asyncio
async def test_create_expense_currency_mismatch_422(app, db, make_user, make_trip, make_attendee):
    creator = await make_user()
    trip = await make_trip(creator=creator, base_currency="USD")
    a2 = await make_attendee(trip, display_name="B")
    payer = trip.creator_attendee

    splits = [
        {"attendee_id": str(payer.id), "share_type": "equal"},
        {"attendee_id": str(a2.id), "share_type": "equal"},
    ]
    body = {
        "payer_attendee_id": str(payer.id),
        "description": "Cena",
        "amount": "100.00",
        "currency": "MXN",  # mismatched!
        "expense_date": str(date(2026, 5, 2)),
        "splits": splits,
    }
    _override(app, creator, db)
    async with await _client(app) as c:
        r = await c.post(f"/trips/{trip.id}/expenses", json=body)
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["code"] == "currency_must_match_trip_base"
