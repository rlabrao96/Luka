"""Tests for the email-ingest reverse-match path.

When a Plaid pending counterpart already exists at the moment an email
arrives, ingest must skip the email INSERT and enrich the Plaid row in
place — preventing the long-lived duplicate that previously sat in the
Pendientes UI until Plaid settled.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.reconciliation.dedup import (
    consolidate_email_values_into_plaid,
    find_plaid_match_for_email_values,
)
from modules.transactions.models import Transaction


async def _seed(db):
    user = User(
        id=uuid.uuid4(),
        email=f"rev-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="Rev Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency="USD",
    )
    db.add(user)
    await db.flush()
    hh = Household(id=uuid.uuid4(), name="Rev HH", type="individual")
    db.add(hh)
    await db.flush()
    db.add(HouseholdMember(household_id=hh.id, user_id=user.id, role="owner"))
    await db.flush()
    acc = BankAccount(
        id=uuid.uuid4(),
        household_id=hh.id,
        user_id=user.id,
        bank_name="BofA",
        account_type="personal",
        currency="USD",
        is_active=True,
    )
    db.add(acc)
    await db.flush()
    return user, hh, acc


@pytest.mark.asyncio
async def test_finds_pending_plaid_counterpart_by_values(db):
    user, hh, acc = await _seed(db)
    when = datetime.now(timezone.utc) - timedelta(days=1)

    plaid_pending = Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=hh.id,
        bank_account_id=acc.id,
        raw_merchant_name="Uber Eats",
        amount=Decimal("-27.43"),
        currency="USD",
        transaction_date=when,
        source="plaid",
        source_type="plaid",
        status="pending",
        transaction_type="expense",
        plaid_transaction_id=f"plaid_{uuid.uuid4().hex[:12]}",
    )
    db.add(plaid_pending)
    await db.flush()

    match = await find_plaid_match_for_email_values(
        db,
        user_id=user.id,
        raw_merchant_name="Uber Eats",
        amount=Decimal("-27.43"),
        currency="USD",
        transaction_date=when,
        transaction_type="expense",
        bank_account_id=acc.id,
        transfer_to_account_id=None,
    )
    assert match is not None
    assert match.id == plaid_pending.id


@pytest.mark.asyncio
async def test_no_match_when_currency_differs(db):
    user, hh, acc = await _seed(db)
    when = datetime.now(timezone.utc) - timedelta(days=1)

    plaid_pending = Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=hh.id,
        bank_account_id=acc.id,
        raw_merchant_name="Uber Eats",
        amount=Decimal("-27.43"),
        currency="CLP",
        transaction_date=when,
        source="plaid",
        source_type="plaid",
        status="pending",
        transaction_type="expense",
        plaid_transaction_id=f"plaid_{uuid.uuid4().hex[:12]}",
    )
    db.add(plaid_pending)
    await db.flush()

    match = await find_plaid_match_for_email_values(
        db,
        user_id=user.id,
        raw_merchant_name="Uber Eats",
        amount=Decimal("-27.43"),
        currency="USD",
        transaction_date=when,
        transaction_type="expense",
        bank_account_id=acc.id,
        transfer_to_account_id=None,
    )
    assert match is None


@pytest.mark.asyncio
async def test_consolidate_applies_transfer_typing(db):
    user, hh, acc = await _seed(db)
    other = BankAccount(
        id=uuid.uuid4(),
        household_id=hh.id,
        user_id=user.id,
        bank_name="Chase",
        account_type="personal",
        currency="USD",
        is_active=True,
    )
    db.add(other)
    await db.flush()

    when = datetime.now(timezone.utc) - timedelta(days=1)
    plaid_pending = Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=hh.id,
        bank_account_id=acc.id,
        raw_merchant_name="Pago Tarjeta ****3100",
        amount=Decimal("-500.00"),
        currency="USD",
        transaction_date=when,
        source="plaid",
        source_type="plaid",
        status="pending",
        transaction_type="expense",
        category="Other",
        plaid_transaction_id=f"plaid_{uuid.uuid4().hex[:12]}",
    )
    db.add(plaid_pending)
    await db.flush()

    await consolidate_email_values_into_plaid(
        db,
        plaid_pending,
        transaction_type="transfer",
        transfer_to_account_id=other.id,
    )
    await db.flush()

    res = await db.execute(select(Transaction).where(Transaction.id == plaid_pending.id))
    reloaded = res.scalar_one()
    assert reloaded.transaction_type == "transfer"
    assert reloaded.category is None
    assert reloaded.transfer_to_account_id == other.id
