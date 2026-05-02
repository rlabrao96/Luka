"""Trip ↔ budget aggregator integration test — Phase 6 Task 6.4.

Spec ``docs/superpowers/specs/2026-04-30-viajes-trips-design.md`` §5.3.

────────────────────────────────────────────────────────────────────────────
Implementation reality (decision: xfail with v1.1 follow-up)
────────────────────────────────────────────────────────────────────────────

The existing budget aggregator (``backend/modules/budgets/v2_service.py``,
~1500 lines, multiple call sites) computes per-category totals by summing
the **full** ``Transaction.amount``. Household-shared expenses are filtered
via ``transaction_splits.split_type``, but the share value itself is the
whole transaction — there is no per-row share carving for households.

Trip splits live in a fundamentally different table
(``trip_expense_splits.share_amount``). Honouring them requires a new
LEFT JOIN against ``trip_expenses + trip_expense_splits`` plus a join
that maps the caller's ``user_id`` to a ``TripAttendee.id`` for the
share-amount lookup, and the change reaches into stats, forecasts, and
the Sankey shape.

Per the plan's option (b), the test is marked ``xfail`` and the v1.1
follow-up to extend the budget aggregator is tracked in
``NEXT-STEPS.md``. Once the aggregator is taught about
``trip_expense_splits``, drop the ``xfail`` marker — the test should pass.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# Ensure trip_expenses.transaction_id → transactions.id FK is resolvable.
from modules.transactions import models as _txn_models  # noqa: F401
from modules.trips import service as trips_service
from modules.trips.schemas import (
    CreateAttendeeInput,
    CreateExpenseRequest,
    SplitInput,
)


async def _make_household(db):
    from modules.households.models import Household

    h = Household(id=uuid.uuid4(), name="H", type="individual")
    db.add(h)
    await db.flush()
    return h


@pytest.mark.xfail(
    reason=(
        "Phase 6.4 — budget aggregator extension to consume "
        "trip_expense_splits.share_amount is pending (v1.1)."
    ),
    strict=False,
)
@pytest.mark.asyncio
async def test_trip_split_reflected_in_personal_category_total(
    db: AsyncSession, make_user, make_trip
):
    """Trip-tagged transaction with a 50/50 split contributes only the
    user's ``share_amount`` to their personal category total — NOT the
    full transaction amount."""
    from modules.budgets.v2_service import _fetch_month_transactions
    from modules.transactions.models import Transaction

    user = await make_user()
    other = await make_user(email=f"o_{uuid.uuid4().hex[:6]}@test.cl")
    h = await _make_household(db)
    trip = await make_trip(
        creator=user,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 7),
        base_currency="USD",
    )
    other_a = await trips_service.add_attendee(
        db, trip, user, CreateAttendeeInput(email=other.email)
    )

    # Transaction: $100 expense in Restaurantes, paid by user.
    # USD transactions store cents per Plaid + email-parser convention.
    txn = Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=h.id,
        bank_account_id=None,
        raw_merchant_name="Restaurant",
        amount=Decimal("-10000"),
        currency="USD",
        transaction_date=datetime(2026, 5, 3, tzinfo=timezone.utc),
        source="manual",
        source_type="manual",
        status="settled",
        transaction_type="expense",
        category="Restaurantes",
    )
    db.add(txn)
    await db.flush()

    # Trip expense + 50/50 split links this txn → user's share is $50.
    await trips_service.create_expense(
        db,
        trip,
        user,
        CreateExpenseRequest(
            payer_attendee_id=trip.creator_attendee.id,
            description="Restaurant",
            amount=Decimal("100.00"),
            currency=trip.base_currency,
            expense_date=date(2026, 5, 3),
            transaction_id=txn.id,
            splits=[
                SplitInput(
                    attendee_id=trip.creator_attendee.id,
                    share_type="custom_amount",
                    share_amount=Decimal("50.00"),
                ),
                SplitInput(
                    attendee_id=other_a.id,
                    share_type="custom_amount",
                    share_amount=Decimal("50.00"),
                ),
            ],
        ),
    )
    await db.flush()

    txns = await _fetch_month_transactions(
        db,
        view="personal",
        user_id=user.id,
        household_id=h.id,
        month=date(2026, 5, 1),
        currency="USD",
    )

    # Aggregate by category, applying trip split.
    total_for_restaurantes = Decimal("0")
    for t in txns:
        if t.category != "Restaurantes":
            continue
        total_for_restaurantes += abs(Decimal(str(t.amount)))

    # Expected: caller contributes only their $50 share, not the full $100.
    # Today the aggregator returns $100 (full amount), which is the
    # behaviour Task 6.4 v1.1 will fix.
    assert total_for_restaurantes == Decimal(
        "50.00"
    ), f"expected user's share=$50 to count, got {total_for_restaurantes}"
