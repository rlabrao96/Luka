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

    job_tx_ids = review_job.transaction_ids  # list of UUID strings, or None
    tx_id_uuids = [uuid.UUID(tid) for tid in job_tx_ids] if job_tx_ids else None

    # Find canonicals via the job's transactions (covers known + new merchants)
    card_query = (
        select(
            CanonicalMerchant.id,
            CanonicalMerchant.display_name,
            CanonicalMerchant.default_category,
            CanonicalMerchant.is_verified,
            func.array_agg(Merchant.raw_name).label("raw_names"),
        )
        .join(Merchant, Merchant.canonical_merchant_id == CanonicalMerchant.id)
        .join(Transaction, Transaction.raw_merchant_name == Merchant.raw_name)
    )
    if tx_id_uuids:
        card_query = card_query.where(Transaction.id.in_(tx_id_uuids))
    else:
        # Legacy fallback: use review_job_id on canonical
        card_query = card_query.where(
            Transaction.user_id == user_id,
            CanonicalMerchant.review_job_id == job_id,
        )
    # Only show unreviewed merchants
    card_query = card_query.where(CanonicalMerchant.is_verified.is_(False))
    card_query = card_query.group_by(CanonicalMerchant.id)

    result = await db.execute(card_query)
    rows = result.all()

    cards = []
    for row in rows:
        unique_names = list(set(row.raw_names))

        # Base filter: user's transactions for these merchant names
        base_where = [
            Transaction.user_id == user_id,
            Transaction.raw_merchant_name.in_(unique_names),
        ]

        # Try scoped first, fall back to unscoped if no results
        def _build_where():
            w = list(base_where)
            if tx_id_uuids:
                w.append(Transaction.id.in_(tx_id_uuids))
            return w

        stats = await db.execute(
            select(
                func.count().label("count"),
                func.sum(Transaction.amount).label("total"),
            ).where(*_build_where())
        )
        stat = stats.one()

        # If scoped query returned nothing, fall back to unscoped
        use_scope = tx_id_uuids and stat.count > 0
        if not use_scope and tx_id_uuids:
            stats = await db.execute(
                select(
                    func.count().label("count"),
                    func.sum(Transaction.amount).label("total"),
                ).where(*base_where)
            )
            stat = stats.one()

        tx_where = list(base_where)
        if use_scope:
            tx_where.append(Transaction.id.in_(tx_id_uuids))

        tx_q = await db.execute(
            select(
                Transaction.raw_merchant_name,
                Transaction.transaction_date,
                Transaction.amount,
            )
            .where(*tx_where)
            .order_by(Transaction.transaction_date.desc())
        )
        transactions_info = [
            {
                "raw_name": r.raw_merchant_name,
                "date": r.transaction_date.strftime("%d-%b-%Y") if r.transaction_date else None,
                "amount": float(r.amount) if r.amount else 0,
            }
            for r in tx_q.all()
        ]

        # Get LLM suggestions from the first linked merchant
        merchant_result = await db.execute(
            select(Merchant).where(Merchant.raw_name == unique_names[0])
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
                "transactions": transactions_info,
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

    # Use explicit category or fall back to canonical's default
    effective_category = category or merchant.default_category

    # Apply category to linked transactions
    if effective_category:
        # Load job to get transaction_ids scope
        job_result = await db.execute(
            select(MerchantReviewJob).where(MerchantReviewJob.id == job_id)
        )
        review_job = job_result.scalar_one_or_none()
        job_tx_ids = review_job.transaction_ids if review_job else None

        linked_merchants = await db.execute(
            select(Merchant.raw_name).where(Merchant.canonical_merchant_id == canonical_id)
        )
        raw_names = [r[0] for r in linked_merchants.all()]
        if raw_names:
            where_clauses = [
                Transaction.user_id == user_id,
                Transaction.raw_merchant_name.in_(raw_names),
            ]
            if job_tx_ids:
                where_clauses.append(Transaction.id.in_([uuid.UUID(tid) for tid in job_tx_ids]))
            await db.execute(
                Transaction.__table__.update()
                .where(*where_clauses)
                .values(category=effective_category)
            )

    # Increment reviewed count on the job
    job = await db.execute(select(MerchantReviewJob).where(MerchantReviewJob.id == job_id))
    review_job = job.scalar_one_or_none()
    if review_job:
        review_job.reviewed_count += 1
        review_job.updated_at = datetime.now(timezone.utc)

        # Check if all merchants are now reviewed — clean up job + notification
        if review_job.total_merchants and review_job.reviewed_count >= review_job.total_merchants:
            notification_id = review_job.notification_id

            # Unlink canonicals from this job
            await db.execute(
                CanonicalMerchant.__table__.update()
                .where(CanonicalMerchant.review_job_id == job_id)
                .values(review_job_id=None)
            )

            # Delete the review job
            await db.delete(review_job)
            await db.flush()

            # Delete the notification
            if notification_id:
                notif = await db.execute(
                    select(Notification).where(Notification.id == notification_id)
                )
                n = notif.scalar_one_or_none()
                if n:
                    await db.delete(n)

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


async def dismiss_review(db: AsyncSession, user_id: uuid.UUID, job_id: uuid.UUID) -> bool:
    """Dismiss a review — accept all proposed categories, delete job and notification."""
    result = await db.execute(
        select(MerchantReviewJob).where(
            MerchantReviewJob.id == job_id,
            MerchantReviewJob.user_id == user_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        return False

    # Pre-applied categories are kept as-is (user accepts defaults)

    # Unlink canonicals from this job
    await db.execute(
        CanonicalMerchant.__table__.update()
        .where(CanonicalMerchant.review_job_id == job_id)
        .values(review_job_id=None)
    )

    # Delete notification
    notification_id = job.notification_id
    job.notification_id = None
    await db.flush()
    if notification_id:
        notif = await db.execute(select(Notification).where(Notification.id == notification_id))
        n = notif.scalar_one_or_none()
        if n:
            await db.delete(n)

    # Delete the review job
    await db.delete(job)
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
