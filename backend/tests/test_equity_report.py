"""Couples equity report (P12)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import Household, HouseholdMember
from modules.households.service import get_equity_report
from modules.transactions.models import Transaction, TransactionSplit


async def _seed(db, ratio=None):
    a = User(
        id=uuid.uuid4(),
        email=f"a-{uuid.uuid4().hex[:6]}@t.cl",
        full_name="Ana",
        email_provider="gmail",
        whatsapp_verified=False,
    )
    b = User(
        id=uuid.uuid4(),
        email=f"b-{uuid.uuid4().hex[:6]}@t.cl",
        full_name="Beto",
        email_provider="gmail",
        whatsapp_verified=False,
    )
    db.add_all([a, b])
    await db.flush()
    h = Household(id=uuid.uuid4(), name="EQ HH", type="couple")
    if ratio:
        h.split_ratio = ratio
    db.add(h)
    await db.flush()
    now = datetime.now(timezone.utc)
    db.add(
        HouseholdMember(
            household_id=h.id, user_id=a.id, role="owner", joined_at=now - timedelta(days=3)
        )
    )
    db.add(HouseholdMember(household_id=h.id, user_id=b.id, role="member", joined_at=now))
    await db.flush()
    return a, b, h


async def _shared(db, user, h, amount, when):
    tx = Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=h.id,
        raw_merchant_name="EQ",
        amount=Decimal(amount),
        currency="CLP",
        transaction_date=when,
        source="connect",
        source_type="connect",
        status="settled",
        transaction_type="expense",
    )
    db.add(tx)
    await db.flush()
    db.add(TransactionSplit(transaction_id=tx.id, split_type="shared"))
    await db.flush()


async def test_equity_report_nets_by_join_order_ratio(db):
    a, b, h = await _seed(db, ratio=[70, 30])
    now = datetime.now(timezone.utc)
    # This month: A paid 100k of shared spending; B paid 0.
    await _shared(db, a, h, "-100000", now)

    report = await get_equity_report(db, h.id, months=2, currency="CLP")
    assert report["currency"] == "CLP"
    current = report["months"][-1]
    assert current["total"] == Decimal("100000")

    by_name = {m["full_name"]: m for m in current["members"]}
    # A (joined first, ratio 70) expected 70000 → fronted +30000.
    assert by_name["Ana"]["expected"] == Decimal("70000")
    assert by_name["Ana"]["net"] == Decimal("30000")
    # B expected 30000, paid 0 → net -30000.
    assert by_name["Beto"]["net"] == Decimal("-30000")
    # Nets always cancel out.
    assert sum(m["net"] for m in current["members"]) == Decimal("0")


async def test_equity_report_zero_months_are_present(db):
    a, b, h = await _seed(db)
    report = await get_equity_report(db, h.id, months=3, currency="CLP")
    assert len(report["months"]) == 3
    for month in report["months"]:
        assert month["total"] == Decimal("0")
        assert all(m["net"] == Decimal("0") for m in month["members"])
