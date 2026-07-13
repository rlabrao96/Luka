"""Shared-card charge classification — pending, dual-visibility, four-way sort,
effective-payer. Real DB, savepoint-rollback db fixture (no mocks)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

import modules.merchants.models  # noqa: F401
import modules.notifications.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.transactions.models import Transaction


async def _couple(db):
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


async def _shared_card(db, owner, hh):
    acct = BankAccount(
        id=uuid.uuid4(),
        household_id=hh.id,
        user_id=owner.id,
        bank_name="American Express",
        account_type="shared_card",
        account_kind="credit_card",
        account_name="Platinum",
        currency="USD",
        is_active=True,
    )
    db.add(acct)
    await db.flush()
    return acct


async def _charge(
    db, owner, hh, acct, amount="-40.00", needs_classification=False, ttype="expense"
):
    txn = Transaction(
        id=uuid.uuid4(),
        user_id=owner.id,
        household_id=hh.id,
        bank_account_id=acct.id,
        raw_merchant_name="Sephora",
        amount=Decimal(amount),
        currency="USD",
        transaction_date=datetime.now(timezone.utc),
        source="plaid",
        source_type="plaid",
        status="settled",
        transaction_type=ttype,
        needs_classification=needs_classification,
    )
    db.add(txn)
    await db.flush()
    return txn


async def test_needs_classification_and_shared_card_persist(db):
    rafael, camila, hh = await _couple(db)
    acct = await _shared_card(db, rafael, hh)
    assert acct.account_type == "shared_card"
    txn = await _charge(db, rafael, hh, acct, needs_classification=True)
    row = (await db.execute(select(Transaction).where(Transaction.id == txn.id))).scalar_one()
    assert row.needs_classification is True
