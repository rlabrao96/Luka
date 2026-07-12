"""CSV export endpoints (P5): transactions + trip ledger.

Real DB, savepoint-rolled-back. Auth via dependency override.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

# Register models for FK resolution.
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.households.models import Household, HouseholdMember
from modules.transactions.models import Transaction, TransactionSplit


async def _seed_txn(db, user, household, amount="-4500", currency="CLP"):
    tx = Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=household.id,
        raw_merchant_name="JUMBO EXPORT",
        amount=Decimal(amount),
        currency=currency,
        transaction_date=datetime.now(timezone.utc),
        source="connect",
        source_type="connect",
        status="settled",
        transaction_type="expense",
    )
    db.add(tx)
    await db.flush()
    db.add(TransactionSplit(transaction_id=tx.id, split_type="personal"))
    await db.flush()
    return tx


async def test_transactions_export_csv(app, db, make_user, http_client):
    from core.database import get_db
    from core.security import get_current_user

    user = await make_user()
    h = Household(id=uuid.uuid4(), name="Export HH", type="couple")
    db.add(h)
    await db.flush()
    db.add(HouseholdMember(household_id=h.id, user_id=user.id, role="owner"))
    await db.flush()
    await _seed_txn(db, user, h)

    async def _db():
        yield db

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = _db
    try:
        res = await http_client.get("/transactions/export", headers={"Authorization": "Bearer x"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    body = res.text
    assert "JUMBO EXPORT" in body
    # CLP is zero-decimal: major units == stored units, negative sign kept.
    assert "-4500" in body


async def test_trip_export_csv(app, db, make_user, make_trip, make_attendee, http_client):
    from core.database import get_db
    from core.security import get_current_user
    from modules.trips.models import TripExpense, TripExpenseSplit

    trip = await make_trip(base_currency="USD")
    creator = trip.creator_user
    other = await make_attendee(trip, display_name="Externo")

    exp = TripExpense(
        trip_id=trip.id,
        payer_attendee_id=trip.creator_attendee.id,
        description="Cena grupo",
        amount=Decimal("90.00"),
        currency="USD",
        expense_date=trip.start_date,
        created_by_user_id=creator.id,
    )
    db.add(exp)
    await db.flush()
    db.add_all(
        [
            TripExpenseSplit(
                trip_expense_id=exp.id,
                attendee_id=trip.creator_attendee.id,
                share_amount=Decimal("45.00"),
                share_type="equal",
            ),
            TripExpenseSplit(
                trip_expense_id=exp.id,
                attendee_id=other.id,
                share_amount=Decimal("45.00"),
                share_type="equal",
            ),
        ]
    )
    await db.flush()

    async def _db():
        yield db

    app.dependency_overrides[get_current_user] = lambda: creator
    app.dependency_overrides[get_db] = _db
    try:
        res = await http_client.get(
            f"/trips/{trip.id}/export", headers={"Authorization": "Bearer x"}
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    body = res.text
    assert "Cena grupo" in body
    assert "Externo" in body
    assert "45.00" in body
