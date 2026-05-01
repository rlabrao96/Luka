"""Tests for ``modules.trips.balances`` — Phase 4 v1.

Covers ``compute_balances`` (DB-driven, reads expenses + settlements) and
``smart_settle_plan`` (pure greedy reduction). The pure plan also gets a
property-based check via Hypothesis.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from hypothesis import given, settings, strategies as st

# Ensure SQLAlchemy can resolve trip_expenses.transaction_id → transactions.id FK.
from modules.transactions import models as _txn_models  # noqa: F401
from modules.trips import service as trips_service
from modules.trips.balances import compute_balances, smart_settle_plan
from modules.trips.schemas import (
    BalanceEntry,
    CreateAttendeeInput,
    CreateExpenseRequest,
    CreateSettlementRequest,
    SplitInput,
)


# ---------------------------------------------------------------------------
# compute_balances — DB-backed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_balance_simple_2_attendees(db, make_user, make_trip, make_attendee):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    other = await make_attendee(trip, display_name="B")
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
                SplitInput(attendee_id=other.id, share_type="equal"),
            ],
        ),
    )
    balances = await compute_balances(trip.id, db)
    by_id = {b.attendee_id: b.net_in_base for b in balances}
    assert by_id[trip.creator_attendee.id] == Decimal("50.00")
    assert by_id[other.id] == Decimal("-50.00")


@pytest.mark.asyncio
async def test_balance_3_attendees_equal(db, make_user, make_trip, make_attendee):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    b = await make_attendee(trip, display_name="B")
    c = await make_attendee(trip, display_name="C")
    await trips_service.create_expense(
        db,
        trip,
        creator,
        CreateExpenseRequest(
            payer_attendee_id=trip.creator_attendee.id,
            description="d",
            amount=Decimal("90.00"),
            currency=trip.base_currency,
            expense_date=date(2026, 5, 2),
            splits=[
                SplitInput(attendee_id=trip.creator_attendee.id, share_type="equal"),
                SplitInput(attendee_id=b.id, share_type="equal"),
                SplitInput(attendee_id=c.id, share_type="equal"),
            ],
        ),
    )
    balances = await compute_balances(trip.id, db)
    by_id = {x.attendee_id: x.net_in_base for x in balances}
    assert by_id[trip.creator_attendee.id] == Decimal("60.00")
    assert by_id[b.id] == Decimal("-30.00")
    assert by_id[c.id] == Decimal("-30.00")


@pytest.mark.asyncio
async def test_balance_with_settlement_reduces_debt(db, make_user, make_trip):
    creator = await make_user()
    other_user = await make_user(email="other_bal@example.com")
    trip = await make_trip(creator=creator)
    other_attendee = await trips_service.add_attendee(
        db,
        trip,
        creator,
        CreateAttendeeInput(email=other_user.email),
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
                SplitInput(attendee_id=other_attendee.id, share_type="equal"),
            ],
        ),
    )
    # other settles $30 to creator
    await trips_service.create_settlement(
        db,
        trip,
        other_user,
        CreateSettlementRequest(
            from_attendee_id=other_attendee.id,
            to_attendee_id=trip.creator_attendee.id,
            amount=Decimal("30.00"),
            currency=trip.base_currency,
        ),
    )
    balances = await compute_balances(trip.id, db)
    by_id = {b.attendee_id: b.net_in_base for b in balances}
    assert by_id[trip.creator_attendee.id] == Decimal("20.00")
    assert by_id[other_attendee.id] == Decimal("-20.00")


@pytest.mark.asyncio
async def test_balance_excludes_deleted_expenses(db, make_user, make_trip, make_attendee):
    creator = await make_user()
    trip = await make_trip(creator=creator)
    other = await make_attendee(trip, display_name="B")
    expense = await trips_service.create_expense(
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
                SplitInput(attendee_id=other.id, share_type="equal"),
            ],
        ),
    )
    await trips_service.delete_expense(db, trip.id, expense.id, creator)
    balances = await compute_balances(trip.id, db)
    for b in balances:
        assert b.net_in_base == Decimal("0")


# ---------------------------------------------------------------------------
# smart_settle_plan — pure
# ---------------------------------------------------------------------------


def _make_balance(net_str: str) -> BalanceEntry:
    return BalanceEntry(
        attendee_id=uuid4(),
        attendee_display_name="x",
        net_in_base=Decimal(net_str),
    )


def test_smart_settle_3_attendee_triangle():
    balances = [
        _make_balance("60"),
        _make_balance("-30"),
        _make_balance("-30"),
    ]
    plan = smart_settle_plan(balances, "USD")
    assert len(plan) == 2
    total = sum((s.amount for s in plan), Decimal("0"))
    assert total == Decimal("60")


def test_smart_settle_zero_nets_no_transfers():
    balances = [_make_balance("0"), _make_balance("0"), _make_balance("0")]
    plan = smart_settle_plan(balances, "USD")
    assert plan == []


def test_smart_settle_at_most_n_minus_1():
    balances = [
        _make_balance("100"),
        _make_balance("50"),
        _make_balance("-30"),
        _make_balance("-60"),
        _make_balance("-60"),
    ]
    plan = smart_settle_plan(balances, "USD")
    assert len(plan) <= len(balances) - 1


@given(
    st.lists(
        st.decimals(
            min_value=Decimal("-1000"),
            max_value=Decimal("1000"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        ),
        min_size=2,
        max_size=6,
    )
)
@settings(max_examples=100, deadline=None)
def test_smart_settle_property_zeros_balances(initial):
    # Force the list to sum to zero by adjusting the last element
    s = sum(initial[:-1], Decimal("0"))
    initial = list(initial[:-1]) + [-s]
    balances = [_make_balance(str(v)) for v in initial]
    n = len(balances)
    plan = smart_settle_plan(balances, "USD")
    # Property 1: at most n-1 transfers (could be 0 if all near-zero)
    assert len(plan) <= max(0, n - 1)
    # Property 2: applying the plan zeroes every net within ε
    nets = {b.attendee_id: Decimal(b.net_in_base) for b in balances}
    for tr in plan:
        nets[tr.from_attendee_id] += tr.amount
        nets[tr.to_attendee_id] -= tr.amount
    for v in nets.values():
        assert abs(v) <= Decimal("0.01"), f"net {v} not zeroed"
