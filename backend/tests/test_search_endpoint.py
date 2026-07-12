"""Global transaction search (P3)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.households.models import Household, HouseholdMember
from modules.transactions.models import Transaction, TransactionSplit
from modules.transactions.service import search_transactions


async def _seed(db, make_user):
    user = await make_user()
    h = Household(id=uuid.uuid4(), name="Search HH", type="couple")
    db.add(h)
    await db.flush()
    db.add(HouseholdMember(household_id=h.id, user_id=user.id, role="owner"))
    await db.flush()

    def tx(name, amount, category=None):
        return Transaction(
            id=uuid.uuid4(),
            user_id=user.id,
            household_id=h.id,
            raw_merchant_name=name,
            amount=Decimal(amount),
            currency="CLP",
            transaction_date=datetime.now(timezone.utc),
            source="connect",
            source_type="connect",
            status="settled",
            transaction_type="expense",
            category=category,
        )

    rows = [
        tx("UBER TRIP SANTIAGO", "-8990", "Transporte"),
        tx("JUMBO MAIPU", "-45990", "Supermercado"),
        tx("NETFLIX.COM", "-12990", "Streaming"),
    ]
    db.add_all(rows)
    await db.flush()
    for r in rows:
        db.add(TransactionSplit(transaction_id=r.id, split_type="personal"))
    await db.flush()
    return user


async def test_search_by_merchant(db, make_user):
    user = await _seed(db, make_user)
    out = await search_transactions(db, user.id, q="uber")
    assert len(out) == 1
    assert out[0]["raw_merchant_name"] == "UBER TRIP SANTIAGO"


async def test_search_by_category(db, make_user):
    user = await _seed(db, make_user)
    out = await search_transactions(db, user.id, q="Supermerc")
    assert len(out) == 1
    assert out[0]["raw_merchant_name"] == "JUMBO MAIPU"


async def test_search_by_amount(db, make_user):
    user = await _seed(db, make_user)
    out = await search_transactions(db, user.id, q="45990")
    assert len(out) == 1
    assert out[0]["raw_merchant_name"] == "JUMBO MAIPU"


async def test_search_never_leaks_other_users(db, make_user):
    await _seed(db, make_user)
    stranger = await make_user()
    out = await search_transactions(db, stranger.id, q="uber")
    assert out == []
