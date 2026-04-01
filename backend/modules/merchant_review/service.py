import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from modules.merchant_review.models import CanonicalMerchant, MerchantReviewJob
from modules.merchants.models import Merchant
from modules.notifications.models import Notification
from modules.transactions.models import Transaction

logger = logging.getLogger(__name__)


async def _get_or_create_canonical(
    db: AsyncSession, display_name: str, review_job_id: uuid.UUID | None = None
) -> dict:
    """Get existing or create new canonical merchant. Returns dict with id, display_name, is_new."""
    result = await db.execute(
        select(CanonicalMerchant).where(CanonicalMerchant.display_name == display_name)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return {"id": str(existing.id), "display_name": existing.display_name, "is_new": False}

    try:
        nested = await db.begin_nested()  # SAVEPOINT — only rolls back this insert on conflict
        canonical = CanonicalMerchant(display_name=display_name, review_job_id=review_job_id)
        db.add(canonical)
        await db.flush()
        return {"id": str(canonical.id), "display_name": canonical.display_name, "is_new": True}
    except IntegrityError:
        await nested.rollback()
        result = await db.execute(
            select(CanonicalMerchant).where(CanonicalMerchant.display_name == display_name)
        )
        existing = result.scalar_one()
        return {"id": str(existing.id), "display_name": existing.display_name, "is_new": False}


async def _link_merchants_to_canonical(
    db: AsyncSession, raw_names: list[str], canonical_id: uuid.UUID
) -> None:
    """Link merchant rows to their canonical merchant."""
    for raw_name in raw_names:
        result = await db.execute(select(Merchant).where(Merchant.raw_name == raw_name))
        merchant = result.scalar_one_or_none()
        if merchant and not merchant.canonical_merchant_id:
            merchant.canonical_merchant_id = canonical_id


async def create_canonicals_from_groups(
    db: AsyncSession, groups: list[dict], review_job_id: uuid.UUID | None = None
) -> list[dict]:
    """Create canonical merchants from LLM grouping output. Returns list of created/linked canonicals."""
    results = []
    for group in groups:
        info = await _get_or_create_canonical(db, group["display_name"], review_job_id)
        canonical_id = uuid.UUID(info["id"])
        await _link_merchants_to_canonical(db, group["raw_names"], canonical_id)
        results.append(info)
    return results


async def get_review_cards(db: AsyncSession, job_id: uuid.UUID, user_id: uuid.UUID) -> list[dict]:
    """Get all canonical merchants for a review job, with aggregated transaction data."""
    job = await db.execute(
        select(MerchantReviewJob).where(
            MerchantReviewJob.id == job_id,
            MerchantReviewJob.user_id == user_id,
        )
    )
    review_job = job.scalar_one_or_none()
    if not review_job:
        return []

    result = await db.execute(
        select(
            CanonicalMerchant.id,
            CanonicalMerchant.display_name,
            CanonicalMerchant.default_category,
            CanonicalMerchant.is_verified,
            func.array_agg(Merchant.raw_name).label("raw_names"),
        )
        .join(Merchant, Merchant.canonical_merchant_id == CanonicalMerchant.id)
        .join(Transaction, Transaction.raw_merchant_name == Merchant.raw_name)
        .where(
            Transaction.user_id == user_id,
            CanonicalMerchant.review_job_id == job_id,
        )
        .group_by(CanonicalMerchant.id)
    )
    rows = result.all()

    cards = []
    for row in rows:
        # Get transaction stats for this canonical merchant
        stats = await db.execute(
            select(
                func.count().label("count"),
                func.sum(Transaction.amount).label("total"),
            ).where(
                Transaction.user_id == user_id,
                Transaction.raw_merchant_name.in_(row.raw_names),
            )
        )
        stat = stats.one()

        # Get LLM suggestions from the first linked merchant
        merchant_result = await db.execute(
            select(Merchant).where(Merchant.raw_name == row.raw_names[0])
        )
        merchant = merchant_result.scalar_one_or_none()

        cards.append(
            {
                "canonical_merchant_id": str(row.id),
                "display_name": row.display_name,
                "default_category": row.default_category,
                "llm_suggested_categories": merchant.llm_suggested_categories or []
                if merchant
                else [],
                "raw_names": list(set(row.raw_names)),
                "transaction_count": stat.count,
                "total_amount": float(stat.total or 0),
                "is_verified": row.is_verified,
            }
        )

    return cards


async def approve_merchant(
    db: AsyncSession,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    canonical_id: uuid.UUID,
    display_name: str | None,
    category: str | None,
) -> bool:
    """Approve (and optionally edit) a canonical merchant."""
    canonical = await db.execute(
        select(CanonicalMerchant).where(CanonicalMerchant.id == canonical_id)
    )
    merchant = canonical.scalar_one_or_none()
    if not merchant:
        return False

    if display_name:
        merchant.display_name = display_name
    if category:
        merchant.default_category = category
    merchant.is_verified = True
    merchant.updated_at = datetime.now(timezone.utc)

    # Update all linked transactions with the category
    if category:
        linked_merchants = await db.execute(
            select(Merchant.raw_name).where(Merchant.canonical_merchant_id == canonical_id)
        )
        raw_names = [r[0] for r in linked_merchants.all()]
        if raw_names:
            await db.execute(
                Transaction.__table__.update()
                .where(
                    Transaction.user_id == user_id,
                    Transaction.raw_merchant_name.in_(raw_names),
                    Transaction.category.is_(None),
                )
                .values(category=category)
            )

    # Increment reviewed count on the job
    job = await db.execute(select(MerchantReviewJob).where(MerchantReviewJob.id == job_id))
    review_job = job.scalar_one_or_none()
    if review_job:
        review_job.reviewed_count += 1
        review_job.updated_at = datetime.now(timezone.utc)

    await db.commit()
    return True


async def skip_review(db: AsyncSession, user_id: uuid.UUID, job_id: uuid.UUID) -> bool:
    """Skip entire review — auto-accept all LLM values."""
    result = await db.execute(
        select(MerchantReviewJob).where(
            MerchantReviewJob.id == job_id,
            MerchantReviewJob.user_id == user_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        return False

    job.status = "skipped"
    job.completed_at = datetime.now(timezone.utc)
    job.updated_at = datetime.now(timezone.utc)

    # Also dismiss the notification
    if job.notification_id:
        notif = await db.execute(select(Notification).where(Notification.id == job.notification_id))
        notification = notif.scalar_one_or_none()
        if notification:
            notification.status = "dismissed"
            notification.updated_at = datetime.now(timezone.utc)

    await db.commit()
    return True


async def get_review_status(db: AsyncSession, job_id: uuid.UUID, user_id: uuid.UUID) -> dict | None:
    result = await db.execute(
        select(MerchantReviewJob).where(
            MerchantReviewJob.id == job_id,
            MerchantReviewJob.user_id == user_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        return None
    return {
        "job_id": str(job.id),
        "status": job.status,
        "total_merchants": job.total_merchants,
        "reviewed_count": job.reviewed_count,
    }
