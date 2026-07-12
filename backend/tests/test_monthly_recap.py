"""Monthly recap (P4): computation, idempotency, silence on empty months."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.households.models import Household, HouseholdMember
from modules.notifications.models import Notification
from modules.notifications.monthly_recap import (
    build_recap_text,
    send_monthly_recap_for_user,
)
from modules.transactions.models import Transaction, TransactionSplit
from sqlalchemy import select


def _month_start(dt):
    return dt.replace(day=1, hour=12, minute=0, second=0, microsecond=0)


async def _seed_user_with_spend(db, make_user):
    user = await make_user(preferred_currency="CLP")
    h = Household(id=uuid.uuid4(), name="Recap HH", type="couple")
    db.add(h)
    await db.flush()
    db.add(HouseholdMember(household_id=h.id, user_id=user.id, role="owner"))
    await db.flush()

    now = datetime.now(timezone.utc)
    prev_month = _month_start(now) - timedelta(days=5)  # lands in previous month
    tx = Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=h.id,
        raw_merchant_name="JUMBO RECAP",
        amount=Decimal("-120000"),
        currency="CLP",
        transaction_date=prev_month,
        source="connect",
        source_type="connect",
        status="settled",
        transaction_type="expense",
        category="Supermercado",
    )
    db.add(tx)
    await db.flush()
    db.add(TransactionSplit(transaction_id=tx.id, split_type="personal"))
    await db.flush()
    return user


async def test_recap_sends_once_and_is_idempotent(db, make_user, monkeypatch):
    user = await _seed_user_with_spend(db, make_user)

    sent_first = await send_monthly_recap_for_user(db, str(user.id))
    assert sent_first is True

    notifs = (
        (
            await db.execute(
                select(Notification).where(
                    Notification.user_id == user.id,
                    Notification.type == "monthly_recap",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(notifs) == 1
    assert notifs[0].payload["total"] == 120000

    # Second run: idempotent, no duplicate.
    sent_again = await send_monthly_recap_for_user(db, str(user.id))
    assert sent_again is False


async def test_recap_silent_when_no_activity(db, make_user):
    user = await make_user(preferred_currency="CLP")
    sent = await send_monthly_recap_for_user(db, str(user.id))
    assert sent is False


def test_recap_text_shape():
    body = build_recap_text(
        month_label="Junio 2026",
        currency="CLP",
        total=450000,
        prev_total=400000,
        movers=[("Restaurantes", 60000), ("Transporte", -20000)],
        settlement_line=None,
    )
    assert "Junio 2026" in body
    assert "CLP 450000" in body
    assert "% más" in body  # 50000/400000 = 12.5% → banker-rounds to 12
    assert "Restaurantes" in body
