"""Tests for merchant_review notification merging + empty-notif suppression.

Covers `_finalize_review_notification` in `jobs/tasks.py`:

- Empty job (no unverified canonicals) → no notification created.
- Non-empty job, no candidate → notification created (existing behavior).
- Non-empty job, unactioned candidate exists → existing notif updated,
  count merged, status reset to unread, timestamp bumped, no second row.
- Non-empty job, actioned candidate exists → new notification created.
- Non-empty job, candidate exists but new job has zero merchants → existing
  notification untouched.

Uses the savepoint `db` fixture from conftest.py so all rows roll back.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

# Register every model so Base.metadata resolves all FKs at flush time.
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from jobs.tasks import _finalize_review_notification
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.merchant_review.models import CanonicalMerchant, MerchantReviewJob
from modules.merchants.models import Merchant
from modules.notifications.models import Notification
from modules.transactions.models import Transaction


async def _seed_user(db) -> tuple[User, Household, BankAccount]:
    user = User(
        id=uuid.uuid4(),
        email=f"merge-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="Merge Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency="CLP",
    )
    db.add(user)
    await db.flush()

    hh = Household(id=uuid.uuid4(), name="Merge HH", type="individual")
    db.add(hh)
    await db.flush()

    db.add(HouseholdMember(household_id=hh.id, user_id=user.id, role="owner"))
    await db.flush()

    acc = BankAccount(
        id=uuid.uuid4(),
        household_id=hh.id,
        user_id=user.id,
        bank_name="Banco Test",
        account_type="personal",
        currency="CLP",
        is_active=True,
    )
    db.add(acc)
    await db.flush()
    return user, hh, acc


async def _seed_canonical_with_tx(
    db,
    *,
    user: User,
    hh: Household,
    acc: BankAccount,
    review_job_id: uuid.UUID,
    is_verified: bool = False,
    raw_name_suffix: str | None = None,
) -> Transaction:
    suffix = raw_name_suffix or uuid.uuid4().hex[:6]
    canonical = CanonicalMerchant(
        id=uuid.uuid4(),
        display_name=f"Test Merchant {suffix}",
        is_verified=is_verified,
        review_job_id=review_job_id,
    )
    db.add(canonical)
    await db.flush()

    raw_name = f"RAW MERCHANT {suffix}"
    merchant = Merchant(
        id=uuid.uuid4(),
        raw_name=raw_name,
        normalized_name=raw_name.lower(),
        canonical_merchant_id=canonical.id,
    )
    db.add(merchant)
    await db.flush()

    tx = Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=hh.id,
        bank_account_id=acc.id,
        raw_merchant_name=raw_name,
        amount=Decimal("-1000"),
        currency="CLP",
        transaction_date=datetime.now(timezone.utc) - timedelta(days=1),
        source="connect",
        source_type="connect",
        status="settled",
        transaction_type="expense",
    )
    db.add(tx)
    await db.flush()
    return tx


async def _make_job(
    db,
    *,
    user: User,
    transaction_ids: list[uuid.UUID] | None = None,
    notification: Notification | None = None,
    completed: bool = False,
) -> MerchantReviewJob:
    job = MerchantReviewJob(
        id=uuid.uuid4(),
        user_id=user.id,
        status="ready",
        transaction_ids=[str(t) for t in transaction_ids] if transaction_ids else None,
        notification_id=notification.id if notification else None,
        completed_at=datetime.now(timezone.utc) if completed else None,
    )
    db.add(job)
    await db.flush()
    return job


# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_job_does_not_create_notification(db):
    user, _, _ = await _seed_user(db)
    job = await _make_job(db, user=user)  # no canonicals at all

    await _finalize_review_notification(db, job)
    await db.flush()

    notifs = (
        (await db.execute(select(Notification).where(Notification.user_id == user.id)))
        .scalars()
        .all()
    )
    assert notifs == []
    assert job.notification_id is None


@pytest.mark.asyncio
async def test_non_empty_job_no_candidate_creates_notification(db):
    user, hh, acc = await _seed_user(db)
    job = await _make_job(db, user=user)
    await _seed_canonical_with_tx(db, user=user, hh=hh, acc=acc, review_job_id=job.id)
    # Use legacy scope (no transaction_ids) so review_job_id linkage applies.

    await _finalize_review_notification(db, job)
    await db.flush()

    notifs = (
        (await db.execute(select(Notification).where(Notification.user_id == user.id)))
        .scalars()
        .all()
    )
    assert len(notifs) == 1
    assert notifs[0].title == "1 comercios listos para revisar"
    assert job.notification_id == notifs[0].id


@pytest.mark.asyncio
async def test_unactioned_candidate_merges_into_existing(db):
    user, hh, acc = await _seed_user(db)

    # Existing notification + job with one unverified canonical.
    existing_notif = Notification(
        id=uuid.uuid4(),
        user_id=user.id,
        type="merchant_review",
        title="1 comercios listos para revisar",
        status="unread",
        payload={"sync_job_id": "old"},
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    db.add(existing_notif)
    await db.flush()

    existing_job = await _make_job(db, user=user, notification=existing_notif)
    await _seed_canonical_with_tx(
        db,
        user=user,
        hh=hh,
        acc=acc,
        review_job_id=existing_job.id,
        raw_name_suffix="EXIST",
    )

    # New job (no notification yet) with one more unverified canonical.
    new_job = await _make_job(db, user=user)
    await _seed_canonical_with_tx(
        db,
        user=user,
        hh=hh,
        acc=acc,
        review_job_id=new_job.id,
        raw_name_suffix="NEW",
    )

    old_created_at = existing_notif.created_at

    await _finalize_review_notification(db, new_job)
    await db.flush()

    # No second notification was created.
    notifs = (
        (await db.execute(select(Notification).where(Notification.user_id == user.id)))
        .scalars()
        .all()
    )
    assert len(notifs) == 1
    merged = notifs[0]
    assert merged.id == existing_notif.id
    assert merged.title == "2 comercios listos para revisar"
    assert merged.status == "unread"
    assert merged.created_at > old_created_at
    assert merged.payload["sync_job_id"] == str(existing_job.id)

    # New job was deleted; its canonical was re-stamped to the existing job.
    deleted = (
        await db.execute(select(MerchantReviewJob).where(MerchantReviewJob.id == new_job.id))
    ).scalar_one_or_none()
    assert deleted is None

    canon_for_new = (
        (
            await db.execute(
                select(CanonicalMerchant).where(CanonicalMerchant.review_job_id == existing_job.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(canon_for_new) == 2  # existing + re-stamped new


@pytest.mark.asyncio
async def test_actioned_candidate_does_not_merge(db):
    user, hh, acc = await _seed_user(db)

    actioned_notif = Notification(
        id=uuid.uuid4(),
        user_id=user.id,
        type="merchant_review",
        title="1 comercios listos para revisar",
        status="actioned",  # not in (unread, read)
        payload={"sync_job_id": "old"},
    )
    db.add(actioned_notif)
    await db.flush()
    await _make_job(db, user=user, notification=actioned_notif)

    new_job = await _make_job(db, user=user)
    await _seed_canonical_with_tx(db, user=user, hh=hh, acc=acc, review_job_id=new_job.id)

    await _finalize_review_notification(db, new_job)
    await db.flush()

    notifs = (
        (
            await db.execute(
                select(Notification)
                .where(Notification.user_id == user.id)
                .order_by(Notification.created_at)
            )
        )
        .scalars()
        .all()
    )
    assert len(notifs) == 2
    new_notif = next(n for n in notifs if n.id != actioned_notif.id)
    assert new_notif.title == "1 comercios listos para revisar"
    assert new_job.notification_id == new_notif.id


@pytest.mark.asyncio
async def test_unactioned_candidate_with_empty_new_job_leaves_notif_alone(db):
    user, hh, acc = await _seed_user(db)

    existing_notif = Notification(
        id=uuid.uuid4(),
        user_id=user.id,
        type="merchant_review",
        title="1 comercios listos para revisar",
        status="unread",
        payload={"sync_job_id": "old"},
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    db.add(existing_notif)
    await db.flush()

    existing_job = await _make_job(db, user=user, notification=existing_notif)
    await _seed_canonical_with_tx(
        db,
        user=user,
        hh=hh,
        acc=acc,
        review_job_id=existing_job.id,
    )
    await db.refresh(existing_notif)
    old_title = existing_notif.title
    old_created_at = existing_notif.created_at

    # New job with NO canonicals at all → merges into existing but adds zero
    # unverified, so the notification should not be bumped/downgraded.
    new_job = await _make_job(db, user=user)

    await _finalize_review_notification(db, new_job)
    await db.flush()

    await db.refresh(existing_notif)
    assert existing_notif.title == old_title
    assert existing_notif.created_at == old_created_at

    # New job still gets cleaned up (its work — even if empty — was merged).
    deleted = (
        await db.execute(select(MerchantReviewJob).where(MerchantReviewJob.id == new_job.id))
    ).scalar_one_or_none()
    assert deleted is None
