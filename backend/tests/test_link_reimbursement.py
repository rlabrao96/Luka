"""Tests for link_reimbursement_group / unlink_reimbursement_group.

Real DB via the `db` savepoint fixture. The reimbursement-group flow is the
"second link type" the user picks from the Vincular dialog: N+1 transactions
sharing a reimbursement_group_id net to zero in spending totals (e.g. work
pays back several receipts with one inflow).

Distinct from transfer pairing in three ways:
  - cardinality is N+1 (not strictly 2)
  - source can be plaid/connect/email (not bank-only)
  - transaction_type is NOT changed (rows stay expense/income)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.transactions.models import Transaction
from modules.transactions.service import (
    link_reimbursement_group,
    unlink_reimbursement_group,
    ServiceError,
)


async def _seed_user_household(db, *, currency: str = "USD"):
    user = User(
        id=uuid.uuid4(),
        email=f"rg-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="RG Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency=currency,
    )
    db.add(user)
    await db.flush()
    hh = Household(id=uuid.uuid4(), name="RG Hogar", type="individual")
    db.add(hh)
    await db.flush()
    db.add(HouseholdMember(household_id=hh.id, user_id=user.id, role="owner"))
    await db.flush()
    return user, hh


async def _seed_account(db, user, hh, *, name="Checking", currency="USD"):
    account = BankAccount(
        id=uuid.uuid4(),
        household_id=hh.id,
        user_id=user.id,
        bank_name=f"Bank-{name}",
        account_name=name,
        account_type="personal",
        currency=currency,
        is_active=True,
    )
    db.add(account)
    await db.flush()
    return account


def _tx(
    *,
    user,
    hh,
    account,
    amount: Decimal,
    when: datetime,
    currency: str = "USD",
    source_type: str = "plaid",
    source: str = "plaid",
    transaction_type: str = "expense",
    transfer_pair_id=None,
    refund_pair_id=None,
    reimbursement_group_id=None,
) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=hh.id,
        bank_account_id=account.id if account else None,
        raw_merchant_name="School",
        amount=amount,
        currency=currency,
        transaction_date=when,
        source=source,
        source_type=source_type,
        status="settled",
        transaction_type=transaction_type,
        transfer_pair_id=transfer_pair_id,
        refund_pair_id=refund_pair_id,
        reimbursement_group_id=reimbursement_group_id,
    )


# ── happy paths ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_happy_path_one_inflow_three_expenses_sums_to_zero(db):
    user, hh = await _seed_user_household(db)
    acct = await _seed_account(db, user, hh)
    when = datetime.now(timezone.utc)
    inflow = _tx(
        user=user,
        hh=hh,
        account=acct,
        amount=Decimal("1500.00"),
        when=when,
        transaction_type="income",
    )
    e1 = _tx(user=user, hh=hh, account=acct, amount=Decimal("-500.00"), when=when)
    e2 = _tx(user=user, hh=hh, account=acct, amount=Decimal("-300.00"), when=when)
    e3 = _tx(user=user, hh=hh, account=acct, amount=Decimal("-700.00"), when=when)
    db.add_all([inflow, e1, e2, e3])
    await db.flush()

    result = await link_reimbursement_group(db, inflow.id, [e1.id, e2.id, e3.id], user.id)
    assert result["reimbursement_group_id"]

    refreshed = (
        (
            await db.execute(
                select(Transaction).where(Transaction.id.in_([inflow.id, e1.id, e2.id, e3.id]))
            )
        )
        .scalars()
        .all()
    )
    group_ids = {r.reimbursement_group_id for r in refreshed}
    assert len(group_ids) == 1 and None not in group_ids
    # transaction_type must NOT change.
    assert {r.transaction_type for r in refreshed if r.id != inflow.id} == {"expense"}
    inflow_row = next(r for r in refreshed if r.id == inflow.id)
    assert inflow_row.transaction_type == "income"
    for r in refreshed:
        assert r.user_edited_fields.get("reimbursement_group_id") is True


@pytest.mark.asyncio
async def test_one_to_one_reimbursement_allowed(db):
    """Cardinality is not restricted to N>1 — a friend reimbursing one
    expense should succeed as a reimbursement (not transfer)."""
    user, hh = await _seed_user_household(db)
    acct = await _seed_account(db, user, hh)
    when = datetime.now(timezone.utc)
    inflow = _tx(
        user=user,
        hh=hh,
        account=acct,
        amount=Decimal("80.00"),
        when=when,
        transaction_type="income",
    )
    expense = _tx(user=user, hh=hh, account=acct, amount=Decimal("-80.00"), when=when)
    db.add_all([inflow, expense])
    await db.flush()

    result = await link_reimbursement_group(db, inflow.id, [expense.id], user.id)
    assert result["reimbursement_group_id"]


@pytest.mark.asyncio
async def test_anchor_can_be_outflow(db):
    """The anchor can also be the lone outflow netting N inflows."""
    user, hh = await _seed_user_household(db)
    acct = await _seed_account(db, user, hh)
    when = datetime.now(timezone.utc)
    out_anchor = _tx(user=user, hh=hh, account=acct, amount=Decimal("-200.00"), when=when)
    in1 = _tx(
        user=user,
        hh=hh,
        account=acct,
        amount=Decimal("80.00"),
        when=when,
        transaction_type="income",
    )
    in2 = _tx(
        user=user,
        hh=hh,
        account=acct,
        amount=Decimal("120.00"),
        when=when,
        transaction_type="income",
    )
    db.add_all([out_anchor, in1, in2])
    await db.flush()

    result = await link_reimbursement_group(db, out_anchor.id, [in1.id, in2.id], user.id)
    assert result["reimbursement_group_id"]


# ── precondition rejections ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rejects_unbalanced_sums(db):
    user, hh = await _seed_user_household(db)
    acct = await _seed_account(db, user, hh)
    when = datetime.now(timezone.utc)
    inflow = _tx(
        user=user,
        hh=hh,
        account=acct,
        amount=Decimal("100.00"),
        when=when,
        transaction_type="income",
    )
    expense = _tx(user=user, hh=hh, account=acct, amount=Decimal("-50.00"), when=when)
    db.add_all([inflow, expense])
    await db.flush()

    with pytest.raises(ServiceError) as exc:
        await link_reimbursement_group(db, inflow.id, [expense.id], user.id)
    assert exc.value.code == "invalid_action"


@pytest.mark.asyncio
async def test_rejects_currency_mismatch(db):
    user, hh = await _seed_user_household(db)
    acct_usd = await _seed_account(db, user, hh, name="USD", currency="USD")
    acct_clp = await _seed_account(db, user, hh, name="CLP", currency="CLP")
    when = datetime.now(timezone.utc)
    inflow = _tx(
        user=user,
        hh=hh,
        account=acct_usd,
        amount=Decimal("100.00"),
        when=when,
        transaction_type="income",
        currency="USD",
    )
    expense = _tx(
        user=user, hh=hh, account=acct_clp, amount=Decimal("-100.00"), when=when, currency="CLP"
    )
    db.add_all([inflow, expense])
    await db.flush()

    with pytest.raises(ServiceError) as exc:
        await link_reimbursement_group(db, inflow.id, [expense.id], user.id)
    assert exc.value.code == "invalid_action"


@pytest.mark.asyncio
async def test_rejects_already_in_transfer_pair(db):
    user, hh = await _seed_user_household(db)
    acct = await _seed_account(db, user, hh)
    when = datetime.now(timezone.utc)
    inflow = _tx(
        user=user,
        hh=hh,
        account=acct,
        amount=Decimal("100.00"),
        when=when,
        transaction_type="income",
    )
    expense = _tx(
        user=user,
        hh=hh,
        account=acct,
        amount=Decimal("-100.00"),
        when=when,
        transfer_pair_id=uuid.uuid4(),
    )
    db.add_all([inflow, expense])
    await db.flush()

    with pytest.raises(ServiceError) as exc:
        await link_reimbursement_group(db, inflow.id, [expense.id], user.id)
    assert exc.value.code == "conflict"


@pytest.mark.asyncio
async def test_rejects_already_in_refund_pair(db):
    user, hh = await _seed_user_household(db)
    acct = await _seed_account(db, user, hh)
    when = datetime.now(timezone.utc)
    inflow = _tx(
        user=user,
        hh=hh,
        account=acct,
        amount=Decimal("100.00"),
        when=when,
        transaction_type="income",
        refund_pair_id=uuid.uuid4(),
    )
    expense = _tx(user=user, hh=hh, account=acct, amount=Decimal("-100.00"), when=when)
    db.add_all([inflow, expense])
    await db.flush()

    with pytest.raises(ServiceError) as exc:
        await link_reimbursement_group(db, inflow.id, [expense.id], user.id)
    assert exc.value.code == "conflict"


@pytest.mark.asyncio
async def test_rejects_already_in_reimbursement_group(db):
    user, hh = await _seed_user_household(db)
    acct = await _seed_account(db, user, hh)
    when = datetime.now(timezone.utc)
    existing_group = uuid.uuid4()
    inflow = _tx(
        user=user,
        hh=hh,
        account=acct,
        amount=Decimal("100.00"),
        when=when,
        transaction_type="income",
        reimbursement_group_id=existing_group,
    )
    expense = _tx(user=user, hh=hh, account=acct, amount=Decimal("-100.00"), when=when)
    db.add_all([inflow, expense])
    await db.flush()

    with pytest.raises(ServiceError) as exc:
        await link_reimbursement_group(db, inflow.id, [expense.id], user.id)
    assert exc.value.code == "conflict"


@pytest.mark.asyncio
async def test_rejects_cross_household(db):
    user_a, hh_a = await _seed_user_household(db)
    user_b, hh_b = await _seed_user_household(db)
    acct_a = await _seed_account(db, user_a, hh_a, name="A")
    acct_b = await _seed_account(db, user_b, hh_b, name="B")
    when = datetime.now(timezone.utc)
    inflow = _tx(
        user=user_a,
        hh=hh_a,
        account=acct_a,
        amount=Decimal("100.00"),
        when=when,
        transaction_type="income",
    )
    expense = _tx(user=user_b, hh=hh_b, account=acct_b, amount=Decimal("-100.00"), when=when)
    db.add_all([inflow, expense])
    await db.flush()

    with pytest.raises(ServiceError) as exc:
        await link_reimbursement_group(db, inflow.id, [expense.id], user_a.id)
    assert exc.value.code == "not_found"


@pytest.mark.asyncio
async def test_rejects_same_sign_anchor_and_counterparts(db):
    user, hh = await _seed_user_household(db)
    acct = await _seed_account(db, user, hh)
    when = datetime.now(timezone.utc)
    a = _tx(user=user, hh=hh, account=acct, amount=Decimal("-100.00"), when=when)
    b = _tx(user=user, hh=hh, account=acct, amount=Decimal("-100.00"), when=when)
    db.add_all([a, b])
    await db.flush()

    with pytest.raises(ServiceError) as exc:
        await link_reimbursement_group(db, a.id, [b.id], user.id)
    assert exc.value.code == "invalid_action"


@pytest.mark.asyncio
async def test_rejects_cross_user_in_same_household(db):
    """All legs must share user_id (single-person reimbursement)."""
    user_a, hh = await _seed_user_household(db)
    # Add a second member to the same household so the SQL membership check passes.
    user_b = User(
        id=uuid.uuid4(),
        email=f"rg2-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="RG2 Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency="USD",
    )
    db.add(user_b)
    await db.flush()
    db.add(HouseholdMember(household_id=hh.id, user_id=user_b.id, role="member"))
    await db.flush()
    acct_a = await _seed_account(db, user_a, hh, name="A")
    acct_b = await _seed_account(db, user_b, hh, name="B")
    when = datetime.now(timezone.utc)
    inflow = _tx(
        user=user_a,
        hh=hh,
        account=acct_a,
        amount=Decimal("100.00"),
        when=when,
        transaction_type="income",
    )
    expense = _tx(user=user_b, hh=hh, account=acct_b, amount=Decimal("-100.00"), when=when)
    db.add_all([inflow, expense])
    await db.flush()

    with pytest.raises(ServiceError) as exc:
        await link_reimbursement_group(db, inflow.id, [expense.id], user_a.id)
    assert exc.value.code == "invalid_action"


@pytest.mark.asyncio
async def test_rejects_anchor_in_counterparts(db):
    user, hh = await _seed_user_household(db)
    acct = await _seed_account(db, user, hh)
    when = datetime.now(timezone.utc)
    a = _tx(
        user=user,
        hh=hh,
        account=acct,
        amount=Decimal("100.00"),
        when=when,
        transaction_type="income",
    )
    db.add(a)
    await db.flush()

    with pytest.raises(ServiceError) as exc:
        await link_reimbursement_group(db, a.id, [a.id], user.id)
    assert exc.value.code == "invalid_action"


# ── unlink ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unlink_clears_all_rows_in_group(db):
    user, hh = await _seed_user_household(db)
    acct = await _seed_account(db, user, hh)
    when = datetime.now(timezone.utc)
    inflow = _tx(
        user=user,
        hh=hh,
        account=acct,
        amount=Decimal("200.00"),
        when=when,
        transaction_type="income",
    )
    e1 = _tx(user=user, hh=hh, account=acct, amount=Decimal("-100.00"), when=when)
    e2 = _tx(user=user, hh=hh, account=acct, amount=Decimal("-100.00"), when=when)
    db.add_all([inflow, e1, e2])
    await db.flush()

    linked = await link_reimbursement_group(db, inflow.id, [e1.id, e2.id], user.id)
    group_id = uuid.UUID(linked["reimbursement_group_id"])

    result = await unlink_reimbursement_group(db, group_id, user.id)
    assert result["unlinked"] == 3

    refreshed = (
        (await db.execute(select(Transaction).where(Transaction.id.in_([inflow.id, e1.id, e2.id]))))
        .scalars()
        .all()
    )
    assert all(r.reimbursement_group_id is None for r in refreshed)
    for r in refreshed:
        assert "reimbursement_group_id" not in (r.user_edited_fields or {})


@pytest.mark.asyncio
async def test_unlink_unknown_group_returns_not_found(db):
    user, _ = await _seed_user_household(db)
    with pytest.raises(ServiceError) as exc:
        await unlink_reimbursement_group(db, uuid.uuid4(), user.id)
    assert exc.value.code == "not_found"


@pytest.mark.asyncio
async def test_unlink_cross_household_rejection(db):
    user_a, hh_a = await _seed_user_household(db)
    user_b, _ = await _seed_user_household(db)
    acct = await _seed_account(db, user_a, hh_a)
    when = datetime.now(timezone.utc)
    inflow = _tx(
        user=user_a,
        hh=hh_a,
        account=acct,
        amount=Decimal("100.00"),
        when=when,
        transaction_type="income",
    )
    expense = _tx(user=user_a, hh=hh_a, account=acct, amount=Decimal("-100.00"), when=when)
    db.add_all([inflow, expense])
    await db.flush()
    linked = await link_reimbursement_group(db, inflow.id, [expense.id], user_a.id)
    gid = uuid.UUID(linked["reimbursement_group_id"])

    with pytest.raises(ServiceError) as exc:
        await unlink_reimbursement_group(db, gid, user_b.id)
    assert exc.value.code == "not_found"
