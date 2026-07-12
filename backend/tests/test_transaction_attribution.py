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


async def test_effective_owner_and_predicate(db):
    from modules.transactions.attribution import attributed_to_clause, effective_owner_id

    rafael, camila, hh = await _couple(db)
    txn = await _charge(db, rafael, hh)
    attr = TransactionAttribution(
        transaction_id=txn.id,
        attributed_to_user_id=camila.id,
        attributed_by_user_id=rafael.id,
        status="active",
    )
    db.add(attr)
    await db.flush()

    assert effective_owner_id(rafael.id, attr) == camila.id
    assert effective_owner_id(rafael.id, None) == rafael.id
    attr.status = "rejected"
    assert effective_owner_id(rafael.id, attr) == rafael.id  # rejected → back to owner

    # Predicate: Camila's rows = her own OR active-attributed-to-her.
    attr.status = "active"
    await db.flush()
    rows = (
        (
            await db.execute(
                select(Transaction.id)
                .outerjoin(
                    TransactionAttribution,
                    TransactionAttribution.transaction_id == Transaction.id,
                )
                .where(attributed_to_clause(camila.id))
            )
        )
        .scalars()
        .all()
    )
    assert txn.id in rows


async def test_hand_off_reject_and_re_handoff(db):
    from modules.notifications.models import Notification
    from modules.transactions.attribution import hand_off, reject, resolve_recipient

    rafael, camila, hh = await _couple(db)
    txn = await _charge(db, rafael, hh)
    db.add(TransactionSplit(transaction_id=txn.id, split_type="personal"))
    await db.flush()

    assert await resolve_recipient(db, hh.id, rafael.id) == camila.id

    await hand_off(db, txn, sender_id=rafael.id, recipient_id=camila.id)
    await db.flush()
    attr = (
        await db.execute(
            select(TransactionAttribution).where(TransactionAttribution.transaction_id == txn.id)
        )
    ).scalar_one()
    assert attr.status == "active"
    split = (
        await db.execute(select(TransactionSplit).where(TransactionSplit.transaction_id == txn.id))
    ).scalar_one()
    assert split.split_type == "partner"
    notif = (
        await db.execute(select(Notification).where(Notification.type == "charge_attributed"))
    ).scalar_one()
    assert notif.user_id == camila.id

    await reject(db, attr.id, by_user_id=camila.id)
    await db.flush()
    await db.refresh(attr)
    await db.refresh(split)
    assert attr.status == "rejected"
    assert split.split_type == "personal"
    assert (
        await db.execute(select(Notification).where(Notification.type == "attribution_rejected"))
    ).scalar_one().user_id == rafael.id

    await hand_off(db, txn, sender_id=rafael.id, recipient_id=camila.id)
    await db.flush()
    rows = (
        (
            await db.execute(
                select(TransactionAttribution).where(
                    TransactionAttribution.transaction_id == txn.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1 and rows[0].status == "active"
