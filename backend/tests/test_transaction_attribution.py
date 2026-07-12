# backend/tests/test_transaction_attribution.py
"""Partner-card charge attribution — lifecycle, predicate, privacy.
Real DB, savepoint-rollback ``db`` fixture (no mocks, per CLAUDE.md)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

import modules.merchants.models  # noqa: F401
import modules.notifications.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember  # noqa: F401
from modules.transactions.models import (  # noqa: F401
    Transaction,
    TransactionAttribution,
    TransactionSplit,
)


async def _couple(db):
    """Rafael (owner) + Camila (member) in one household; returns (rafael, camila, hh)."""
    hh = Household(id=uuid.uuid4(), name="HH", type="couple")
    db.add(hh)
    await db.flush()
    users = {}
    for name, role in (("rafael", "owner"), ("camila", "member")):
        u = User(
            id=uuid.uuid4(),
            email=f"{name}-{uuid.uuid4().hex[:8]}@luka.test",
            full_name=name.title(),
            email_provider="gmail",
            whatsapp_verified=False,
            preferred_currency="USD",
        )
        db.add(u)
        await db.flush()
        db.add(HouseholdMember(household_id=hh.id, user_id=u.id, role=role))
        users[name] = u
    await db.flush()
    return users["rafael"], users["camila"], hh


async def _charge(db, owner, hh, amount="-40.00"):
    txn = Transaction(
        id=uuid.uuid4(),
        user_id=owner.id,
        household_id=hh.id,
        raw_merchant_name="Sephora",
        amount=Decimal(amount),
        currency="USD",
        transaction_date=datetime.now(timezone.utc),
        source="plaid",
        source_type="plaid",
        status="settled",
        transaction_type="expense",
    )
    db.add(txn)
    await db.flush()
    return txn


async def test_attribution_row_persists(db):
    rafael, camila, hh = await _couple(db)
    txn = await _charge(db, rafael, hh)
    db.add(
        TransactionAttribution(
            transaction_id=txn.id,
            attributed_to_user_id=camila.id,
            attributed_by_user_id=rafael.id,
            status="active",
        )
    )
    await db.flush()
    row = (
        await db.execute(
            select(TransactionAttribution).where(TransactionAttribution.transaction_id == txn.id)
        )
    ).scalar_one()
    assert row.status == "active"
    assert row.attributed_to_user_id == camila.id
