"""Manual reclassify: scoped merchant-review job over uncategorized txns."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import modules.merchants.models  # noqa: F401
import modules.merchant_review.models  # noqa: F401
import modules.notifications.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.households.models import Household, HouseholdMember
from modules.merchant_review.models import MerchantReviewJob
from modules.transactions.models import Transaction, TransactionSplit
from modules.transactions.service import count_unclassified, reclassify_unclassified
from sqlalchemy import select


async def _seed(db, make_user):
    user = await make_user()
    h = Household(id=uuid.uuid4(), name="RC HH", type="couple")
    db.add(h)
    await db.flush()
    db.add(HouseholdMember(household_id=h.id, user_id=user.id, role="owner"))
    await db.flush()

    now = datetime.now(timezone.utc)

    def tx(cat, when):
        return Transaction(
            id=uuid.uuid4(),
            user_id=user.id,
            household_id=h.id,
            raw_merchant_name="SOME MERCHANT",
            amount=Decimal("-5000"),
            currency="CLP",
            transaction_date=when,
            source="connect",
            source_type="connect",
            status="settled",
            transaction_type="expense",
            category=cat,
        )

    rows = [
        tx(None, now - timedelta(days=2)),  # uncategorized, in range → picked
        tx(None, now - timedelta(days=5)),  # uncategorized, in range → picked
        tx("Supermercado", now - timedelta(days=3)),  # already categorized → skip
        tx(None, now - timedelta(days=40)),  # out of range → skip
    ]
    db.add_all(rows)
    await db.flush()
    for r in rows:
        db.add(TransactionSplit(transaction_id=r.id, split_type="personal"))
    await db.flush()
    return user


async def test_count_and_reclassify_scope(db, make_user):
    user = await _seed(db, make_user)
    since = (datetime.now(timezone.utc) - timedelta(days=10)).date()

    assert await count_unclassified(db, user.id, since=since) == 2

    with patch("jobs.queue.enqueue_job", new_callable=AsyncMock) as enq:
        res = await reclassify_unclassified(db, user.id, since=since)

    assert res["transaction_count"] == 2
    assert res["job_id"] is not None
    enq.assert_awaited_once()

    job = (
        await db.execute(
            select(MerchantReviewJob).where(MerchantReviewJob.id == uuid.UUID(res["job_id"]))
        )
    ).scalar_one()
    assert len(job.transaction_ids) == 2


async def test_reclassify_nothing_to_do(db, make_user):
    user = await make_user()
    since = (datetime.now(timezone.utc) - timedelta(days=10)).date()
    res = await reclassify_unclassified(db, user.id, since=since)
    assert res == {"job_id": None, "transaction_count": 0}
