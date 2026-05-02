"""Tests for the suggestions inbox — Phase 6 Task 6.1.

Spec ``docs/superpowers/specs/2026-04-30-viajes-trips-design.md`` §4.6.

Covers:
- in-window expense surfaces
- subscription-linked transaction excluded (via detected_subscriptions_cache)
- transfer-paired transaction excluded (transfer_pair_id IS NOT NULL)
- already-linked transaction excluded
- soft-deleted trip-link case re-surfaces
- dismissed → not in result
- undismiss → re-surfaces
- per-user isolation
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

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


async def _make_household(db):
    from modules.households.models import Household

    h = Household(id=uuid.uuid4(), name="H", type="individual")
    db.add(h)
    await db.flush()
    return h


_ZERO_DECIMAL = {"CLP", "COP", "JPY", "KRW", "PYG", "VND", "CLF"}


async def _make_transaction(
    db,
    user,
    household,
    *,
    amount=Decimal("-50.00"),
    currency="USD",
    transaction_date=None,
    transaction_type="expense",
    raw_merchant="Coffee shop",
    transfer_pair_id=None,
    refund_pair_id=None,
    reimbursement_group_id=None,
):
    """Insert a transaction. ``amount`` is in major units; this helper scales
    to the production storage convention (integer cents for non-zero-decimal
    currencies)."""
    from modules.transactions.models import Transaction

    if transaction_date is None:
        transaction_date = datetime(2026, 5, 3, tzinfo=timezone.utc)
    stored_amount = amount if currency.upper() in _ZERO_DECIMAL else Decimal(amount) * 100
    txn = Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=household.id,
        bank_account_id=None,
        raw_merchant_name=raw_merchant,
        amount=stored_amount,
        currency=currency,
        transaction_date=transaction_date,
        source="manual",
        source_type="manual",
        status="settled",
        transaction_type=transaction_type,
        transfer_pair_id=transfer_pair_id,
        refund_pair_id=refund_pair_id,
        reimbursement_group_id=reimbursement_group_id,
    )
    db.add(txn)
    await db.flush()
    return txn


@pytest.mark.asyncio
async def test_in_window_expense_surfaces(app, db, make_user, make_trip):
    user = await make_user()
    h = await _make_household(db)
    trip = await make_trip(creator=user, start_date=date(2026, 5, 1), end_date=date(2026, 5, 7))
    txn = await _make_transaction(db, user, h)

    _override(app, user, db)
    async with await _client(app) as c:
        r = await c.get(f"/trips/{trip.id}/suggested-transactions")
    assert r.status_code == 200, r.text
    body = r.json()
    assert any(item["transaction_id"] == str(txn.id) for item in body)


@pytest.mark.asyncio
async def test_transfer_paired_transaction_excluded(app, db, make_user, make_trip):
    user = await make_user()
    h = await _make_household(db)
    trip = await make_trip(creator=user, start_date=date(2026, 5, 1), end_date=date(2026, 5, 7))
    pair_id = uuid.uuid4()
    await _make_transaction(db, user, h, transfer_pair_id=pair_id)

    _override(app, user, db)
    async with await _client(app) as c:
        r = await c.get(f"/trips/{trip.id}/suggested-transactions")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_already_linked_transaction_excluded(app, db, make_user, make_trip):
    user = await make_user()
    h = await _make_household(db)
    trip = await make_trip(creator=user, start_date=date(2026, 5, 1), end_date=date(2026, 5, 7))
    txn = await _make_transaction(db, user, h, amount=Decimal("-50.00"))

    # Link via create_expense.
    await trips_service.create_expense(
        db,
        trip,
        user,
        CreateExpenseRequest(
            payer_attendee_id=trip.creator_attendee.id,
            description="Coffee",
            amount=Decimal("50.00"),
            currency=trip.base_currency,
            expense_date=date(2026, 5, 3),
            transaction_id=txn.id,
            splits=[
                SplitInput(
                    attendee_id=trip.creator_attendee.id,
                    share_type="custom_amount",
                    share_amount=Decimal("50.00"),
                )
            ],
        ),
    )
    await db.flush()

    _override(app, user, db)
    async with await _client(app) as c:
        r = await c.get(f"/trips/{trip.id}/suggested-transactions")
    assert r.status_code == 200
    assert all(item["transaction_id"] != str(txn.id) for item in r.json())


@pytest.mark.asyncio
async def test_soft_deleted_link_resurfaces(app, db, make_user, make_trip):
    user = await make_user()
    h = await _make_household(db)
    trip = await make_trip(creator=user, start_date=date(2026, 5, 1), end_date=date(2026, 5, 7))
    txn = await _make_transaction(db, user, h, amount=Decimal("-50.00"))

    expense = await trips_service.create_expense(
        db,
        trip,
        user,
        CreateExpenseRequest(
            payer_attendee_id=trip.creator_attendee.id,
            description="Coffee",
            amount=Decimal("50.00"),
            currency=trip.base_currency,
            expense_date=date(2026, 5, 3),
            transaction_id=txn.id,
            splits=[
                SplitInput(
                    attendee_id=trip.creator_attendee.id,
                    share_type="custom_amount",
                    share_amount=Decimal("50.00"),
                )
            ],
        ),
    )
    # Soft-delete the trip expense.
    expense.deleted_at = datetime.now(timezone.utc)
    await db.flush()

    _override(app, user, db)
    async with await _client(app) as c:
        r = await c.get(f"/trips/{trip.id}/suggested-transactions")
    assert r.status_code == 200
    assert any(item["transaction_id"] == str(txn.id) for item in r.json())


@pytest.mark.asyncio
async def test_dismiss_removes_then_undismiss_restores(app, db, make_user, make_trip):
    user = await make_user()
    h = await _make_household(db)
    trip = await make_trip(creator=user, start_date=date(2026, 5, 1), end_date=date(2026, 5, 7))
    txn = await _make_transaction(db, user, h)

    _override(app, user, db)
    async with await _client(app) as c:
        # Dismiss
        rd = await c.post(f"/trips/{trip.id}/suggested-transactions/{txn.id}/dismiss")
        assert rd.status_code == 204, rd.text

        r1 = await c.get(f"/trips/{trip.id}/suggested-transactions")
        assert r1.status_code == 200
        assert all(item["transaction_id"] != str(txn.id) for item in r1.json())

        # Undismiss
        ru = await c.delete(f"/trips/{trip.id}/suggested-transactions/{txn.id}/dismiss")
        assert ru.status_code == 204

        r2 = await c.get(f"/trips/{trip.id}/suggested-transactions")
        assert r2.status_code == 200
        assert any(item["transaction_id"] == str(txn.id) for item in r2.json())


@pytest.mark.asyncio
async def test_subscription_linked_excluded(app, db, make_user, make_trip):
    user = await make_user()
    h = await _make_household(db)
    trip = await make_trip(creator=user, start_date=date(2026, 5, 1), end_date=date(2026, 5, 7))
    await _make_transaction(db, user, h, raw_merchant="Netflix")

    # Seed detected_subscriptions_cache.
    items = json.dumps([{"merchant_name": "Netflix", "status": "active", "currency": "USD"}])
    await db.execute(
        text(
            """
            INSERT INTO detected_subscriptions_cache (user_id, result_json, computed_at)
            VALUES (:uid, CAST(:data AS jsonb), NOW())
            ON CONFLICT (user_id) DO UPDATE SET result_json = CAST(:data AS jsonb)
            """
        ),
        {"uid": str(user.id), "data": items},
    )
    await db.flush()

    _override(app, user, db)
    async with await _client(app) as c:
        r = await c.get(f"/trips/{trip.id}/suggested-transactions")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_per_user_isolation(app, db, make_user, make_trip):
    creator = await make_user()
    other = await make_user(email=f"other_{uuid.uuid4().hex[:6]}@test.cl")
    h = await _make_household(db)
    trip = await make_trip(creator=creator, start_date=date(2026, 5, 1), end_date=date(2026, 5, 7))
    await trips_service.add_attendee(db, trip, creator, CreateAttendeeInput(email=other.email))

    # Each user has their own in-window expense.
    txn_creator = await _make_transaction(db, creator, h, raw_merchant="Creator coffee")
    txn_other = await _make_transaction(db, other, h, raw_merchant="Other coffee")

    # Creator sees only their own.
    _override(app, creator, db)
    async with await _client(app) as c:
        r = await c.get(f"/trips/{trip.id}/suggested-transactions")
    assert r.status_code == 200
    ids = {item["transaction_id"] for item in r.json()}
    assert str(txn_creator.id) in ids
    assert str(txn_other.id) not in ids

    # Other sees only theirs.
    _override(app, other, db)
    async with await _client(app) as c:
        r = await c.get(f"/trips/{trip.id}/suggested-transactions")
    assert r.status_code == 200
    ids = {item["transaction_id"] for item in r.json()}
    assert str(txn_other.id) in ids
    assert str(txn_creator.id) not in ids
