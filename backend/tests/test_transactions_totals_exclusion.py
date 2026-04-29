"""Tests for Task 2.10: currency-aware dedup, orphan bucket, exclude_from_totals.

Uses the real-DB savepoint `db` fixture (see conftest.py). All inserts are
rolled back via the SAVEPOINT wrapper — no permanent writes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select

# Register all models so Base.metadata resolves FKs when the session flushes.
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.transactions.models import Transaction
from modules.transactions.service import (
    exclude_from_totals,
    get_pending_transactions,
    is_duplicate_transaction,
)


# ----------------------------------------------------------------- helpers


async def _seed_household(db, *, currency: str = "USD") -> tuple[User, Household, BankAccount]:
    user = User(
        id=uuid.uuid4(),
        email=f"t210-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="T210 Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency=currency,
    )
    db.add(user)
    await db.flush()

    household = Household(id=uuid.uuid4(), name="T210 HH", type="individual")
    db.add(household)
    await db.flush()

    db.add(HouseholdMember(household_id=household.id, user_id=user.id, role="owner"))
    await db.flush()

    account = BankAccount(
        id=uuid.uuid4(),
        household_id=household.id,
        user_id=user.id,
        bank_name="Bank Of America",
        account_type="personal",
        currency=currency,
        is_active=True,
    )
    db.add(account)
    await db.flush()
    return user, household, account


def _tx(
    *,
    user: User,
    household: Household,
    account: BankAccount | None,
    amount: Decimal,
    when: datetime,
    currency: str = "USD",
    bank_name: str = "Bank Of America",
    status: str = "pending",
    source: str = "gmail",
    source_type: str = "email",
    tx_type: str = "expense",
    transfer_pair_id: uuid.UUID | None = None,
    refund_pair_id: uuid.UUID | None = None,
    reimbursement_group_id: uuid.UUID | None = None,
    orphaned_at: datetime | None = None,
    created_at: datetime | None = None,
) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=household.id,
        bank_account_id=account.id if account else None,
        raw_merchant_name="Merchant",
        amount=amount,
        currency=currency,
        transaction_date=when,
        source=source,
        source_type=source_type,
        source_bank_name=bank_name,
        status=status,
        transaction_type=tx_type,
        transfer_pair_id=transfer_pair_id,
        refund_pair_id=refund_pair_id,
        reimbursement_group_id=reimbursement_group_id,
        orphaned_at=orphaned_at,
        created_at=created_at,
    )


# -------------------------------------------------- is_duplicate_transaction


@pytest.mark.asyncio
async def test_is_duplicate_transaction_rejects_different_currency(db):
    user, hh, acc = await _seed_household(db)
    now = datetime.now(timezone.utc)
    db.add(
        _tx(
            user=user,
            household=hh,
            account=acc,
            amount=Decimal("-2000"),
            when=now,
            currency="CLP",
            bank_name="Banco Chile",
            created_at=now,
        )
    )
    await db.flush()

    result = await is_duplicate_transaction(
        db, user.id, 2000, bank_name="Banco Chile", currency="USD"
    )
    assert result is False


@pytest.mark.asyncio
async def test_is_duplicate_transaction_rejects_different_bank_within_5min(db):
    user, hh, acc = await _seed_household(db)
    now = datetime.now(timezone.utc)
    db.add(
        _tx(
            user=user,
            household=hh,
            account=acc,
            amount=Decimal("-100"),
            when=now,
            currency="USD",
            bank_name="Bank Of America",
            created_at=now,
        )
    )
    await db.flush()

    # Tier 1 must not collide across different banks (prior to fix it did).
    # Tier 2 also needs >5min gap to trigger. At T+30s it would not apply anyway.
    result = await is_duplicate_transaction(db, user.id, 100, bank_name="Chase", currency="USD")
    assert result is False


@pytest.mark.asyncio
async def test_is_duplicate_transaction_accepts_same_bank_same_currency_within_5min(db):
    user, hh, acc = await _seed_household(db)
    now = datetime.now(timezone.utc)
    db.add(
        _tx(
            user=user,
            household=hh,
            account=acc,
            amount=Decimal("-100"),
            when=now,
            currency="USD",
            bank_name="Bank Of America",
            created_at=now,
        )
    )
    await db.flush()

    result = await is_duplicate_transaction(
        db, user.id, 100, bank_name="Bank Of America", currency="USD"
    )
    assert result is True


# ---------------------------------------------------- get_pending_transactions


@pytest.mark.asyncio
async def test_get_pending_transactions_populates_unmatched_email_with_orphan_rows(db):
    user, hh, acc = await _seed_household(db)
    now = datetime.now(timezone.utc)
    orphan = _tx(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("-42"),
        when=now - timedelta(days=5),
        status="orphan",
        source="gmail",
        source_type="email",
        orphaned_at=now,
    )
    db.add(orphan)
    await db.flush()

    result = await get_pending_transactions(db, user.id)
    ids = [row["id"] for row in result["unmatched_email"]]
    assert orphan.id in ids


@pytest.mark.asyncio
async def test_get_pending_transactions_does_not_include_orphan_in_awaiting_reconciliation(db):
    user, hh, acc = await _seed_household(db)
    now = datetime.now(timezone.utc)
    orphan = _tx(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("-42"),
        when=now - timedelta(days=5),
        status="orphan",
        source="gmail",
        source_type="email",
        orphaned_at=now,
    )
    db.add(orphan)
    await db.flush()

    result = await get_pending_transactions(db, user.id)
    awaiting_ids = [row["id"] for row in result["awaiting_reconciliation"]]
    assert orphan.id not in awaiting_ids


# ----------------------------------------------------------- exclude_from_totals


async def _sum_amount_for_user(db, user_id: uuid.UUID) -> Decimal:
    q = exclude_from_totals(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.user_id == user_id)
    )
    res = await db.execute(q)
    return Decimal(str(res.scalar_one() or 0))


@pytest.mark.asyncio
async def test_exclude_from_totals_filters_transfer_pair(db):
    user, hh, acc = await _seed_household(db)
    now = datetime.now(timezone.utc)
    pair_id = uuid.uuid4()
    # Transfer pair: two legs, both must be excluded from totals.
    db.add_all(
        [
            _tx(
                user=user,
                household=hh,
                account=acc,
                amount=Decimal("-500"),
                when=now,
                status="settled",
                tx_type="transfer",
                transfer_pair_id=pair_id,
            ),
            _tx(
                user=user,
                household=hh,
                account=acc,
                amount=Decimal("500"),
                when=now,
                status="settled",
                tx_type="transfer",
                transfer_pair_id=pair_id,
            ),
            # A non-paired expense should remain.
            _tx(
                user=user,
                household=hh,
                account=acc,
                amount=Decimal("-25"),
                when=now,
                status="settled",
            ),
        ]
    )
    await db.flush()

    total = await _sum_amount_for_user(db, user.id)
    assert total == Decimal("-25")


@pytest.mark.asyncio
async def test_exclude_from_totals_filters_refund_pair(db):
    user, hh, acc = await _seed_household(db)
    now = datetime.now(timezone.utc)
    pair_id = uuid.uuid4()
    db.add_all(
        [
            _tx(
                user=user,
                household=hh,
                account=acc,
                amount=Decimal("-80"),
                when=now,
                status="settled",
                refund_pair_id=pair_id,
            ),
            _tx(
                user=user,
                household=hh,
                account=acc,
                amount=Decimal("80"),
                when=now,
                status="settled",
                tx_type="income",
                refund_pair_id=pair_id,
            ),
            _tx(
                user=user,
                household=hh,
                account=acc,
                amount=Decimal("-10"),
                when=now,
                status="settled",
            ),
        ]
    )
    await db.flush()

    total = await _sum_amount_for_user(db, user.id)
    assert total == Decimal("-10")


@pytest.mark.asyncio
async def test_exclude_from_totals_filters_reimbursement_group(db):
    """Rows sharing a reimbursement_group_id net to zero in spend totals."""
    user, hh, acc = await _seed_household(db)
    now = datetime.now(timezone.utc)
    gid = uuid.uuid4()
    db.add_all(
        [
            _tx(
                user=user,
                household=hh,
                account=acc,
                amount=Decimal("1500"),
                when=now,
                status="settled",
                tx_type="income",
                reimbursement_group_id=gid,
            ),
            _tx(
                user=user,
                household=hh,
                account=acc,
                amount=Decimal("-500"),
                when=now,
                status="settled",
                reimbursement_group_id=gid,
            ),
            _tx(
                user=user,
                household=hh,
                account=acc,
                amount=Decimal("-300"),
                when=now,
                status="settled",
                reimbursement_group_id=gid,
            ),
            _tx(
                user=user,
                household=hh,
                account=acc,
                amount=Decimal("-700"),
                when=now,
                status="settled",
                reimbursement_group_id=gid,
            ),
            # Untouched expense should still count.
            _tx(
                user=user,
                household=hh,
                account=acc,
                amount=Decimal("-42"),
                when=now,
                status="settled",
            ),
        ]
    )
    await db.flush()

    total = await _sum_amount_for_user(db, user.id)
    assert total == Decimal("-42")


@pytest.mark.asyncio
async def test_exclude_from_totals_filters_orphan(db):
    user, hh, acc = await _seed_household(db)
    now = datetime.now(timezone.utc)
    db.add_all(
        [
            _tx(
                user=user,
                household=hh,
                account=acc,
                amount=Decimal("-999"),
                when=now,
                status="orphan",
                orphaned_at=now,
            ),
            _tx(
                user=user,
                household=hh,
                account=acc,
                amount=Decimal("-15"),
                when=now,
                status="settled",
            ),
        ]
    )
    await db.flush()

    total = await _sum_amount_for_user(db, user.id)
    assert total == Decimal("-15")
