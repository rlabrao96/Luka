"""Verify that ``approve_merchant`` accepts a ``split_type`` argument and applies
it to the ``transaction_splits`` rows for every transaction linked to the
canonical merchant.

Scope rules mirror category application:
  - When the review job has ``transaction_ids``, only those txns are updated.
  - When ``split_type=None``, existing TransactionSplit rows are untouched.
  - User override wins on joint accounts (no server-side coercion).

Real DB, savepoint-rolled-back via the ``db`` fixture in conftest.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

# Register all models for FK resolution.
import modules.merchants.models  # noqa: F401
import modules.notifications.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.merchant_review.models import CanonicalMerchant, MerchantReviewJob
from modules.merchant_review.service import approve_merchant
from modules.merchants.models import Merchant
from modules.transactions.models import Transaction, TransactionSplit


# ---------------------------------------------------------------- helpers


async def _seed_household(db, account_type: str) -> tuple[User, Household, BankAccount]:
    user = User(
        id=uuid.uuid4(),
        email=f"mr-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="MR Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency="CLP",
    )
    db.add(user)
    await db.flush()

    household = Household(id=uuid.uuid4(), name="Test HH", type="couple")
    db.add(household)
    await db.flush()

    db.add(HouseholdMember(household_id=household.id, user_id=user.id, role="owner"))
    await db.flush()

    account = BankAccount(
        id=uuid.uuid4(),
        household_id=household.id,
        user_id=user.id,
        bank_name="BCI",
        account_type=account_type,
        account_kind="checking_account",
        account_name=f"{account_type} Checking",
        currency="CLP",
        is_active=True,
    )
    db.add(account)
    await db.flush()
    return user, household, account


async def _seed_canonical_with_txns(
    db,
    user: User,
    household: Household,
    account: BankAccount,
    raw_name: str,
    initial_split_type: str,
    n: int = 2,
) -> tuple[CanonicalMerchant, MerchantReviewJob, list[Transaction]]:
    merchant = Merchant(id=uuid.uuid4(), raw_name=raw_name)
    db.add(merchant)
    await db.flush()

    canonical = CanonicalMerchant(
        id=uuid.uuid4(),
        display_name=f"Display {raw_name}",
        is_verified=False,
    )
    db.add(canonical)
    await db.flush()

    merchant.canonical_merchant_id = canonical.id
    await db.flush()

    txns: list[Transaction] = []
    for _ in range(n):
        tx = Transaction(
            id=uuid.uuid4(),
            user_id=user.id,
            household_id=household.id,
            bank_account_id=account.id,
            raw_merchant_name=raw_name,
            amount=Decimal("-1500.00"),
            currency="CLP",
            transaction_date=datetime.now(timezone.utc),
            source="connect",
            source_type="connect",
            status="settled",
            transaction_type="expense",
        )
        db.add(tx)
        await db.flush()
        db.add(
            TransactionSplit(
                transaction_id=tx.id,
                split_type=initial_split_type,
            )
        )
        txns.append(tx)
    await db.flush()

    job = MerchantReviewJob(
        id=uuid.uuid4(),
        user_id=user.id,
        status="ready",
        total_merchants=1,
        reviewed_count=0,
        transaction_ids=[str(t.id) for t in txns],
    )
    db.add(job)
    await db.flush()
    canonical.review_job_id = job.id
    await db.flush()
    return canonical, job, txns


async def _split_types(db, tx_ids: list[uuid.UUID]) -> list[str]:
    rows = (
        await db.execute(
            select(TransactionSplit.split_type).where(TransactionSplit.transaction_id.in_(tx_ids))
        )
    ).all()
    return [r[0] for r in rows]


# ---------------------------------------------------------------- tests


async def test_approve_merchant_applies_split_type_to_linked_transactions(db):
    """Personal account, approve with split_type='shared' → all rows become 'shared'."""
    user, household, account = await _seed_household(db, "personal")
    canonical, job, txns = await _seed_canonical_with_txns(
        db, user, household, account, "STARBUCKS_A", initial_split_type="personal"
    )

    ok = await approve_merchant(
        db=db,
        user_id=user.id,
        job_id=job.id,
        canonical_id=canonical.id,
        display_name=None,
        category="food",
        split_type="shared",
    )
    assert ok is True

    types = await _split_types(db, [t.id for t in txns])
    assert len(types) == len(txns)
    assert all(s == "shared" for s in types), f"got {types}"


async def test_approve_merchant_split_type_user_override_wins_on_joint(db):
    """Joint account, approve with split_type='personal' → user override persists."""
    user, household, account = await _seed_household(db, "joint")
    canonical, job, txns = await _seed_canonical_with_txns(
        db, user, household, account, "STARBUCKS_B", initial_split_type="shared"
    )

    ok = await approve_merchant(
        db=db,
        user_id=user.id,
        job_id=job.id,
        canonical_id=canonical.id,
        display_name=None,
        category="food",
        split_type="personal",
    )
    assert ok is True

    types = await _split_types(db, [t.id for t in txns])
    assert all(
        s == "personal" for s in types
    ), f"User override of 'personal' on joint account must win; got {types}"


async def test_approve_merchant_without_split_type_leaves_existing_unchanged(db):
    """No split_type passed → existing TransactionSplit rows untouched."""
    user, household, account = await _seed_household(db, "personal")
    canonical, job, txns = await _seed_canonical_with_txns(
        db, user, household, account, "STARBUCKS_C", initial_split_type="personal"
    )

    ok = await approve_merchant(
        db=db,
        user_id=user.id,
        job_id=job.id,
        canonical_id=canonical.id,
        display_name=None,
        category="food",
    )
    assert ok is True

    types = await _split_types(db, [t.id for t in txns])
    assert all(s == "personal" for s in types), f"expected unchanged 'personal'; got {types}"
