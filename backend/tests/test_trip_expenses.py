"""Tests for ``service.create_expense`` + ``POST /trips/{id}/expenses``.

Phase 3 Tasks 3.1 + 3.2: sign convention, split-sum normalization,
mutual-exclusivity 409 mapping, and basic auth/membership validation.
See spec ``docs/superpowers/specs/2026-04-30-viajes-trips-design.md`` §3.9, §3.10, §4.4.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from modules.auth.models import User  # noqa: F401


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


async def _make_household(db):
    from modules.households.models import Household

    h = Household(id=uuid.uuid4(), name="H", type="individual")
    db.add(h)
    await db.flush()
    return h


async def _make_transaction(db, user, household, amount, currency="USD"):
    from modules.transactions.models import Transaction

    txn = Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=household.id,
        bank_account_id=None,
        raw_merchant_name="Hotel",
        amount=Decimal(str(amount)),
        currency=currency,
        transaction_date=datetime.now(timezone.utc),
        source="manual",
        source_type="manual",
        status="settled",
        transaction_type="expense",
    )
    db.add(txn)
    await db.flush()
    return txn


def _split(attendee_id, *, share_type="equal", share_amount=None, share_percent=None):
    body = {"attendee_id": str(attendee_id), "share_type": share_type}
    if share_amount is not None:
        body["share_amount"] = str(share_amount)
    if share_percent is not None:
        body["share_percent"] = str(share_percent)
    return body


def _payload(payer_id, splits, *, amount="100.00", currency="USD", transaction_id=None):
    body = {
        "payer_attendee_id": str(payer_id),
        "description": "Hotel",
        "amount": str(amount),
        "currency": currency,
        "expense_date": str(date(2026, 5, 2)),
        "splits": splits,
    }
    if transaction_id is not None:
        body["transaction_id"] = str(transaction_id)
    return body


# ---------------------------------------------------------------------------
# Equal split + sign convention
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_expense_equal_split_distributes_evenly(
    app, db, make_user, make_trip, make_attendee
):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    a2 = await make_attendee(trip, display_name="B")
    a3 = await make_attendee(trip, display_name="C")
    a4 = await make_attendee(trip, display_name="D")
    payer = trip.creator_attendee

    splits = [_split(a.id) for a in (payer, a2, a3, a4)]
    _override(app, creator, db)
    async with await _client(app) as c:
        r = await c.post(
            f"/trips/{trip.id}/expenses",
            json=_payload(payer.id, splits, amount="400.00"),
        )
    assert r.status_code == 201, r.text
    body = r.json()
    assert Decimal(body["amount"]) == Decimal("400.00")
    amounts = sorted(Decimal(s["share_amount"]) for s in body["splits"])
    assert amounts == [Decimal("100.00")] * 4


@pytest.mark.asyncio
async def test_create_expense_equal_split_payer_absorbs_remainder(
    app, db, make_user, make_trip, make_attendee
):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    a2 = await make_attendee(trip, display_name="B")
    a3 = await make_attendee(trip, display_name="C")
    payer = trip.creator_attendee

    splits = [_split(a.id) for a in (payer, a2, a3)]
    _override(app, creator, db)
    async with await _client(app) as c:
        r = await c.post(
            f"/trips/{trip.id}/expenses",
            json=_payload(payer.id, splits, amount="100.00"),
        )
    assert r.status_code == 201, r.text
    body = r.json()
    by_id = {s["attendee_id"]: Decimal(s["share_amount"]) for s in body["splits"]}
    assert by_id[str(payer.id)] == Decimal("33.34")
    assert by_id[str(a2.id)] == Decimal("33.33")
    assert by_id[str(a3.id)] == Decimal("33.33")
    assert sum(by_id.values()) == Decimal("100.00")


# ---------------------------------------------------------------------------
# Custom amount
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_expense_custom_amount_must_sum(app, db, make_user, make_trip, make_attendee):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    a2 = await make_attendee(trip, display_name="B")
    a3 = await make_attendee(trip, display_name="C")
    payer = trip.creator_attendee

    # 30 + 30 + 39 = 99 ≠ 100
    splits = [
        _split(payer.id, share_type="custom_amount", share_amount="30.00"),
        _split(a2.id, share_type="custom_amount", share_amount="30.00"),
        _split(a3.id, share_type="custom_amount", share_amount="39.00"),
    ]
    _override(app, creator, db)
    async with await _client(app) as c:
        r = await c.post(
            f"/trips/{trip.id}/expenses",
            json=_payload(payer.id, splits, amount="100.00"),
        )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_expense_custom_amount_passes_when_sums(
    app, db, make_user, make_trip, make_attendee
):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    a2 = await make_attendee(trip, display_name="B")
    a3 = await make_attendee(trip, display_name="C")
    payer = trip.creator_attendee

    splits = [
        _split(payer.id, share_type="custom_amount", share_amount="40.00"),
        _split(a2.id, share_type="custom_amount", share_amount="30.00"),
        _split(a3.id, share_type="custom_amount", share_amount="30.00"),
    ]
    _override(app, creator, db)
    async with await _client(app) as c:
        r = await c.post(
            f"/trips/{trip.id}/expenses",
            json=_payload(payer.id, splits, amount="100.00"),
        )
    assert r.status_code == 201, r.text


# ---------------------------------------------------------------------------
# Custom percent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_expense_custom_percent_normalizes(
    app, db, make_user, make_trip, make_attendee
):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    a2 = await make_attendee(trip, display_name="B")
    a3 = await make_attendee(trip, display_name="C")
    payer = trip.creator_attendee

    splits = [
        _split(payer.id, share_type="custom_percent", share_percent="30"),
        _split(a2.id, share_type="custom_percent", share_percent="30"),
        _split(a3.id, share_type="custom_percent", share_percent="40"),
    ]
    _override(app, creator, db)
    async with await _client(app) as c:
        r = await c.post(
            f"/trips/{trip.id}/expenses",
            json=_payload(payer.id, splits, amount="100.00"),
        )
    assert r.status_code == 201, r.text
    body = r.json()
    by_id = {s["attendee_id"]: Decimal(s["share_amount"]) for s in body["splits"]}
    assert by_id[str(payer.id)] == Decimal("30.00")
    assert by_id[str(a2.id)] == Decimal("30.00")
    assert by_id[str(a3.id)] == Decimal("40.00")
    assert sum(by_id.values()) == Decimal("100.00")


@pytest.mark.asyncio
async def test_create_expense_custom_percent_must_sum_to_100(
    app, db, make_user, make_trip, make_attendee
):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    a2 = await make_attendee(trip, display_name="B")
    payer = trip.creator_attendee

    splits = [
        _split(payer.id, share_type="custom_percent", share_percent="40"),
        _split(a2.id, share_type="custom_percent", share_percent="40"),
    ]
    _override(app, creator, db)
    async with await _client(app) as c:
        r = await c.post(
            f"/trips/{trip.id}/expenses",
            json=_payload(payer.id, splits, amount="100.00"),
        )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Linked transactions: sign + ownership
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_expense_with_transaction_uses_abs(
    app, db, make_user, make_trip, make_attendee
):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    a2 = await make_attendee(trip, display_name="B")
    payer = trip.creator_attendee

    h = await _make_household(db)
    # transactions store USD as integer cents (Plaid + email parser convention),
    # so $400.00 is stored as -40000.
    txn = await _make_transaction(db, creator, h, "-40000")

    splits = [_split(payer.id), _split(a2.id)]
    _override(app, creator, db)
    async with await _client(app) as c:
        r = await c.post(
            f"/trips/{trip.id}/expenses",
            json=_payload(payer.id, splits, amount="400.00", transaction_id=txn.id),
        )
    assert r.status_code == 201, r.text
    body = r.json()
    assert Decimal(body["amount"]) == Decimal("400.00")
    assert body["transaction_id"] == str(txn.id)


@pytest.mark.asyncio
async def test_create_expense_amount_must_match_transaction_abs(
    app, db, make_user, make_trip, make_attendee
):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    a2 = await make_attendee(trip, display_name="B")
    payer = trip.creator_attendee

    h = await _make_household(db)
    txn = await _make_transaction(db, creator, h, "-40000")  # cents

    splits = [_split(payer.id), _split(a2.id)]
    _override(app, creator, db)
    async with await _client(app) as c:
        r = await c.post(
            f"/trips/{trip.id}/expenses",
            json=_payload(payer.id, splits, amount="200.00", transaction_id=txn.id),
        )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_expense_other_users_transaction_403(
    app, db, make_user, make_trip, make_attendee
):
    creator = await make_user()
    other = await make_user()
    trip = await make_trip(creator=creator)
    a2 = await make_attendee(trip, display_name="B")
    payer = trip.creator_attendee

    h = await _make_household(db)
    txn = await _make_transaction(db, other, h, "-40000")  # cents

    splits = [_split(payer.id), _split(a2.id)]
    _override(app, creator, db)
    async with await _client(app) as c:
        r = await c.post(
            f"/trips/{trip.id}/expenses",
            json=_payload(payer.id, splits, amount="400.00", transaction_id=txn.id),
        )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Membership / state validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_expense_payer_not_on_trip_404(app, db, make_user, make_trip, make_attendee):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    payer = trip.creator_attendee

    other_trip = await make_trip(creator=creator, name="Other")
    foreign = other_trip.creator_attendee

    splits = [_split(payer.id)]
    _override(app, creator, db)
    async with await _client(app) as c:
        r = await c.post(
            f"/trips/{trip.id}/expenses",
            json=_payload(foreign.id, splits, amount="100.00"),
        )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_create_expense_split_attendee_not_on_trip_404(
    app, db, make_user, make_trip, make_attendee
):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    payer = trip.creator_attendee

    other_trip = await make_trip(creator=creator, name="Other")
    foreign = other_trip.creator_attendee

    splits = [_split(payer.id), _split(foreign.id)]
    _override(app, creator, db)
    async with await _client(app) as c:
        r = await c.post(
            f"/trips/{trip.id}/expenses",
            json=_payload(payer.id, splits, amount="100.00"),
        )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_create_expense_split_attendee_left_422(app, db, make_user, make_trip, make_attendee):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    a2 = await make_attendee(trip, display_name="B")
    a2.left_at = datetime.now(timezone.utc)
    await db.flush()
    payer = trip.creator_attendee

    splits = [_split(payer.id), _split(a2.id)]
    _override(app, creator, db)
    async with await _client(app) as c:
        r = await c.post(
            f"/trips/{trip.id}/expenses",
            json=_payload(payer.id, splits, amount="100.00"),
        )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# 409 paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_expense_double_link_409(app, db, make_user, make_trip, make_attendee):
    creator = await make_user()
    trip1 = await make_trip(creator=creator, name="Trip 1")
    trip2 = await make_trip(creator=creator, name="Trip 2")
    payer1 = trip1.creator_attendee
    payer2 = trip2.creator_attendee

    h = await _make_household(db)
    txn = await _make_transaction(db, creator, h, "-10000")

    _override(app, creator, db)
    async with await _client(app) as c:
        r1 = await c.post(
            f"/trips/{trip1.id}/expenses",
            json=_payload(payer1.id, [_split(payer1.id)], amount="100.00", transaction_id=txn.id),
        )
        assert r1.status_code == 201, r1.text
        r2 = await c.post(
            f"/trips/{trip2.id}/expenses",
            json=_payload(payer2.id, [_split(payer2.id)], amount="100.00", transaction_id=txn.id),
        )
    assert r2.status_code == 409
    assert r2.json()["detail"]["code"] == "transaction_already_linked"


@pytest.mark.asyncio
async def test_create_expense_409_when_transaction_has_household_splits(
    app, db, make_user, make_trip, make_attendee
):
    from modules.transactions.models import TransactionSplit

    creator = await make_user()
    trip = await make_trip(creator=creator)
    payer = trip.creator_attendee

    h = await _make_household(db)
    txn = await _make_transaction(db, creator, h, "-10000")

    # Pre-existing household split → 409 from BEFORE trigger.
    db.add(TransactionSplit(id=uuid.uuid4(), transaction_id=txn.id, split_type="shared"))
    await db.flush()

    _override(app, creator, db)
    async with await _client(app) as c:
        r = await c.post(
            f"/trips/{trip.id}/expenses",
            json=_payload(payer.id, [_split(payer.id)], amount="100.00", transaction_id=txn.id),
        )
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "joint_account_dual_split_not_supported"


# ---------------------------------------------------------------------------
# PATCH /trips/{trip_id}/expenses/{expense_id} — optimistic concurrency
# ---------------------------------------------------------------------------


async def _create_basic_expense(c, trip, payer, others, amount="100.00"):
    splits = [_split(payer.id)] + [_split(a.id) for a in others]
    r = await c.post(
        f"/trips/{trip.id}/expenses",
        json=_payload(payer.id, splits, amount=amount),
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.asyncio
async def test_patch_expense_with_matching_version_increments(
    app, db, make_user, make_trip, make_attendee
):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    a2 = await make_attendee(trip, display_name="B")
    payer = trip.creator_attendee

    _override(app, creator, db)
    async with await _client(app) as c:
        exp = await _create_basic_expense(c, trip, payer, [a2])
        assert exp["version"] == 1
        r = await c.patch(
            f"/trips/{trip.id}/expenses/{exp['id']}",
            headers={"If-Match": "1"},
            json={"description": "Updated hotel"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["version"] == 2
    assert body["description"] == "Updated hotel"


@pytest.mark.asyncio
async def test_patch_expense_with_stale_version_returns_409(
    app, db, make_user, make_trip, make_attendee
):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    a2 = await make_attendee(trip, display_name="B")
    payer = trip.creator_attendee

    _override(app, creator, db)
    async with await _client(app) as c:
        exp = await _create_basic_expense(c, trip, payer, [a2])
        r1 = await c.patch(
            f"/trips/{trip.id}/expenses/{exp['id']}",
            headers={"If-Match": "1"},
            json={"description": "First"},
        )
        assert r1.status_code == 200
        r2 = await c.patch(
            f"/trips/{trip.id}/expenses/{exp['id']}",
            headers={"If-Match": "1"},
            json={"description": "Second"},
        )
    assert r2.status_code == 409
    detail = r2.json()["detail"]
    assert detail["code"] == "version_conflict"
    assert detail["current_version"] == 2
    assert detail["expense"]["description"] == "First"


@pytest.mark.asyncio
async def test_patch_expense_amount_change_requires_splits(
    app, db, make_user, make_trip, make_attendee
):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    a2 = await make_attendee(trip, display_name="B")
    payer = trip.creator_attendee

    _override(app, creator, db)
    async with await _client(app) as c:
        exp = await _create_basic_expense(c, trip, payer, [a2])
        r = await c.patch(
            f"/trips/{trip.id}/expenses/{exp['id']}",
            headers={"If-Match": "1"},
            json={"amount": "200.00"},
        )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_patch_expense_amount_and_splits_succeeds(
    app, db, make_user, make_trip, make_attendee
):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    a2 = await make_attendee(trip, display_name="B")
    payer = trip.creator_attendee

    _override(app, creator, db)
    async with await _client(app) as c:
        exp = await _create_basic_expense(c, trip, payer, [a2])
        new_splits = [_split(payer.id), _split(a2.id)]
        r = await c.patch(
            f"/trips/{trip.id}/expenses/{exp['id']}",
            headers={"If-Match": "1"},
            json={"amount": "200.00", "splits": new_splits},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["version"] == 2
    assert Decimal(body["amount"]) == Decimal("200.00")
    amounts = sorted(Decimal(s["share_amount"]) for s in body["splits"])
    assert amounts == [Decimal("100.00"), Decimal("100.00")]


@pytest.mark.asyncio
async def test_patch_expense_split_sum_validated(app, db, make_user, make_trip, make_attendee):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    a2 = await make_attendee(trip, display_name="B")
    payer = trip.creator_attendee

    _override(app, creator, db)
    async with await _client(app) as c:
        exp = await _create_basic_expense(c, trip, payer, [a2])
        bad_splits = [
            _split(payer.id, share_type="custom_amount", share_amount="40.00"),
            _split(a2.id, share_type="custom_amount", share_amount="50.00"),
        ]
        r = await c.patch(
            f"/trips/{trip.id}/expenses/{exp['id']}",
            headers={"If-Match": "1"},
            json={"splits": bad_splits},
        )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_patch_expense_change_payer_requires_splits(
    app, db, make_user, make_trip, make_attendee
):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    a2 = await make_attendee(trip, display_name="B")
    payer = trip.creator_attendee

    _override(app, creator, db)
    async with await _client(app) as c:
        exp = await _create_basic_expense(c, trip, payer, [a2])
        r = await c.patch(
            f"/trips/{trip.id}/expenses/{exp['id']}",
            headers={"If-Match": "1"},
            json={"payer_attendee_id": str(a2.id)},
        )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_patch_already_deleted_expense_404(app, db, make_user, make_trip, make_attendee):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    a2 = await make_attendee(trip, display_name="B")
    payer = trip.creator_attendee

    _override(app, creator, db)
    async with await _client(app) as c:
        exp = await _create_basic_expense(c, trip, payer, [a2])
        d = await c.delete(f"/trips/{trip.id}/expenses/{exp['id']}")
        assert d.status_code == 204
        r = await c.patch(
            f"/trips/{trip.id}/expenses/{exp['id']}",
            headers={"If-Match": "1"},
            json={"description": "x"},
        )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /trips/{trip_id}/expenses/{expense_id} — soft delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_expense_soft_deletes(app, db, make_user, make_trip, make_attendee):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    a2 = await make_attendee(trip, display_name="B")
    payer = trip.creator_attendee

    _override(app, creator, db)
    async with await _client(app) as c:
        exp = await _create_basic_expense(c, trip, payer, [a2])
        r = await c.delete(f"/trips/{trip.id}/expenses/{exp['id']}")
    assert r.status_code == 204

    from sqlalchemy import select

    from modules.trips.models import TripExpense

    row = (
        await db.execute(select(TripExpense).where(TripExpense.id == uuid.UUID(exp["id"])))
    ).scalar_one()
    assert row.deleted_at is not None


@pytest.mark.asyncio
async def test_delete_expense_frees_transaction_for_relink(
    app, db, make_user, make_trip, make_attendee
):
    creator = await make_user()
    trip1 = await make_trip(creator=creator, name="Trip 1")
    trip2 = await make_trip(creator=creator, name="Trip 2")
    payer1 = trip1.creator_attendee
    payer2 = trip2.creator_attendee

    h = await _make_household(db)
    txn = await _make_transaction(db, creator, h, "-10000")

    _override(app, creator, db)
    async with await _client(app) as c:
        r1 = await c.post(
            f"/trips/{trip1.id}/expenses",
            json=_payload(payer1.id, [_split(payer1.id)], amount="100.00", transaction_id=txn.id),
        )
        assert r1.status_code == 201, r1.text
        exp1_id = r1.json()["id"]
        d = await c.delete(f"/trips/{trip1.id}/expenses/{exp1_id}")
        assert d.status_code == 204
        # Now the same transaction can be linked to trip2.
        r2 = await c.post(
            f"/trips/{trip2.id}/expenses",
            json=_payload(payer2.id, [_split(payer2.id)], amount="100.00", transaction_id=txn.id),
        )
    assert r2.status_code == 201, r2.text


@pytest.mark.asyncio
async def test_delete_already_deleted_expense_404(app, db, make_user, make_trip, make_attendee):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    a2 = await make_attendee(trip, display_name="B")
    payer = trip.creator_attendee

    _override(app, creator, db)
    async with await _client(app) as c:
        exp = await _create_basic_expense(c, trip, payer, [a2])
        d1 = await c.delete(f"/trips/{trip.id}/expenses/{exp['id']}")
        assert d1.status_code == 204
        d2 = await c.delete(f"/trips/{trip.id}/expenses/{exp['id']}")
    assert d2.status_code == 404
