import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func, text
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
    """Get all canonical merchants for a review job, with aggregated transaction data.

    Batched to ≤4 SQL queries regardless of card count:
      Q1  job lookup (for transaction_ids scope).
      Q2  canonicals + their raw_name list.
      Q3  per-raw_name stats (scoped + unscoped folded via FILTER).
      Q4  per-raw_name top-25 transactions via window function, plus
          a UNION ALL twin tagged scoped/unscoped so the per-canonical
          scope-fallback is resolved in Python without an extra roundtrip.
    LLM suggestions are folded into Q2 by aggregating Merchant.raw_name +
    Merchant.llm_suggested_categories together — we keep the existing
    behavior of using the first linked merchant's suggestions.
    """
    # ---------- Q1: review job ------------------------------------------
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

    # ---------- Q2: canonicals + raw_names + llm_suggestions ------------
    # array_agg on (raw_name, llm_suggested_categories) lets us recover the
    # "first linked merchant's suggestion" without a separate Merchant lookup.
    card_query = (
        select(
            CanonicalMerchant.id,
            CanonicalMerchant.display_name,
            CanonicalMerchant.default_category,
            CanonicalMerchant.is_verified,
            func.array_agg(Merchant.raw_name).label("raw_names"),
            func.array_agg(Merchant.llm_suggested_categories).label("llm_suggestions"),
        )
        .join(Merchant, Merchant.canonical_merchant_id == CanonicalMerchant.id)
        .join(Transaction, Transaction.raw_merchant_name == Merchant.raw_name)
    )
    if tx_id_uuids:
        card_query = card_query.where(Transaction.id.in_(tx_id_uuids))
    else:
        # Legacy fallback: use review_job_id on canonical.
        card_query = card_query.where(
            Transaction.user_id == user_id,
            CanonicalMerchant.review_job_id == job_id,
        )
    card_query = card_query.where(CanonicalMerchant.is_verified.is_(False))
    card_query = card_query.group_by(CanonicalMerchant.id)

    result = await db.execute(card_query)
    rows = result.all()
    if not rows:
        return []

    # Collect every raw_name across canonicals, plus per-canonical first-name lookup.
    all_raw_names: set[str] = set()
    canonical_first_suggestion: dict[uuid.UUID, list] = {}
    for row in rows:
        unique_names = list(dict.fromkeys(row.raw_names))  # preserve order, dedupe
        all_raw_names.update(unique_names)
        # Find suggestion paired with the first raw_name (parallel arrays).
        first_idx = row.raw_names.index(unique_names[0])
        suggestions = row.llm_suggestions or []
        raw_sugg = suggestions[first_idx] if first_idx < len(suggestions) else None
        # asyncpg may surface JSON columns either as decoded list/dict or as a
        # JSON-encoded string depending on registered codecs — handle both.
        if isinstance(raw_sugg, str):
            try:
                parsed = json.loads(raw_sugg)
                canonical_first_suggestion[row.id] = parsed if isinstance(parsed, list) else []
            except (ValueError, TypeError):
                canonical_first_suggestion[row.id] = []
        elif isinstance(raw_sugg, list):
            canonical_first_suggestion[row.id] = raw_sugg
        else:
            canonical_first_suggestion[row.id] = []

    raw_names_list = list(all_raw_names)

    # ---------- Q3: stats per raw_name (scoped + unscoped via FILTER) ---
    # FILTER lets us compute scoped and unscoped aggregates in one pass; the
    # caller picks the scoped numbers when scoped_cnt > 0, else unscoped.
    if tx_id_uuids:
        stats_sql = text(
            """
            SELECT
                t.raw_merchant_name AS raw_name,
                t.currency AS currency,
                COUNT(*) FILTER (WHERE t.id = ANY(:tx_ids)) AS scoped_cnt,
                COALESCE(SUM(t.amount) FILTER (WHERE t.id = ANY(:tx_ids)), 0) AS scoped_total,
                COUNT(*) AS unscoped_cnt,
                COALESCE(SUM(t.amount), 0) AS unscoped_total
            FROM transactions t
            WHERE t.user_id = :uid
              AND t.raw_merchant_name = ANY(:raw_names)
            GROUP BY t.raw_merchant_name, t.currency
            """
        )
        stats_rows = (
            await db.execute(
                stats_sql, {"uid": user_id, "raw_names": raw_names_list, "tx_ids": tx_id_uuids}
            )
        ).all()
    else:
        stats_sql = text(
            """
            SELECT
                t.raw_merchant_name AS raw_name,
                t.currency AS currency,
                COUNT(*) AS scoped_cnt,
                COALESCE(SUM(t.amount), 0) AS scoped_total,
                COUNT(*) AS unscoped_cnt,
                COALESCE(SUM(t.amount), 0) AS unscoped_total
            FROM transactions t
            WHERE t.user_id = :uid
              AND t.raw_merchant_name = ANY(:raw_names)
            GROUP BY t.raw_merchant_name, t.currency
            """
        )
        stats_rows = (
            await db.execute(stats_sql, {"uid": user_id, "raw_names": raw_names_list})
        ).all()

    # Per-raw_name aggregation: a single raw_name may have multiple currencies,
    # but in practice we treat it as a single bucket. Sum across currency rows
    # and remember the first-seen currency (matches old "currency from first tx"
    # semantics — per-merchant txs share currency in the wild).
    stats_by_raw: dict[str, dict] = {}
    for r in stats_rows:
        bucket = stats_by_raw.setdefault(
            r.raw_name,
            {
                "scoped_cnt": 0,
                "scoped_total": 0.0,
                "unscoped_cnt": 0,
                "unscoped_total": 0.0,
                "currency": r.currency or "CLP",
            },
        )
        bucket["scoped_cnt"] += int(r.scoped_cnt or 0)
        bucket["scoped_total"] += float(r.scoped_total or 0)
        bucket["unscoped_cnt"] += int(r.unscoped_cnt or 0)
        bucket["unscoped_total"] += float(r.unscoped_total or 0)

    # ---------- Q4: top-25 transactions per raw_name (window function) --
    # UNION ALL of scoped (priority=1) and unscoped (priority=2) lets us pick
    # the scoped slice when present and fall back to unscoped without firing
    # an extra query. priority=2 rows are only consulted if priority=1 is empty.
    if tx_id_uuids:
        tx_sql = text(
            """
            SELECT raw_merchant_name, transaction_date, amount, currency, priority
            FROM (
                SELECT raw_merchant_name, transaction_date, amount, currency, priority,
                       ROW_NUMBER() OVER (
                           PARTITION BY raw_merchant_name, priority
                           ORDER BY transaction_date DESC
                       ) AS rn
                FROM (
                    SELECT raw_merchant_name, transaction_date, amount, currency, 1 AS priority
                    FROM transactions
                    WHERE user_id = :uid
                      AND raw_merchant_name = ANY(:raw_names)
                      AND id = ANY(:tx_ids)
                    UNION ALL
                    SELECT raw_merchant_name, transaction_date, amount, currency, 2 AS priority
                    FROM transactions
                    WHERE user_id = :uid
                      AND raw_merchant_name = ANY(:raw_names)
                ) u
            ) sub
            WHERE rn <= 25
            ORDER BY raw_merchant_name, priority, transaction_date DESC
            """
        )
        tx_rows = (
            await db.execute(
                tx_sql, {"uid": user_id, "raw_names": raw_names_list, "tx_ids": tx_id_uuids}
            )
        ).all()
    else:
        tx_sql = text(
            """
            SELECT raw_merchant_name, transaction_date, amount, currency, 1 AS priority
            FROM (
                SELECT raw_merchant_name, transaction_date, amount, currency,
                       ROW_NUMBER() OVER (
                           PARTITION BY raw_merchant_name
                           ORDER BY transaction_date DESC
                       ) AS rn
                FROM transactions
                WHERE user_id = :uid
                  AND raw_merchant_name = ANY(:raw_names)
            ) sub
            WHERE rn <= 25
            ORDER BY raw_merchant_name, transaction_date DESC
            """
        )
        tx_rows = (await db.execute(tx_sql, {"uid": user_id, "raw_names": raw_names_list})).all()

    # Bucket transactions by raw_name and priority.
    tx_by_raw_priority: dict[tuple[str, int], list[dict]] = {}
    for r in tx_rows:
        key = (r.raw_merchant_name, int(r.priority))
        tx_by_raw_priority.setdefault(key, []).append(
            {
                "_sort_dt": r.transaction_date,  # real datetime for sorting; stripped before return
                "raw_name": r.raw_merchant_name,
                "date": r.transaction_date.strftime("%d-%b-%Y") if r.transaction_date else None,
                "amount": float(r.amount) if r.amount is not None else 0.0,
                "currency": r.currency or "CLP",
            }
        )

    # ---------- Assemble cards ------------------------------------------
    cards: list[dict] = []
    for row in rows:
        unique_names = list(dict.fromkeys(row.raw_names))

        # Aggregate stats across this canonical's raw_names.
        scoped_cnt = scoped_total = 0
        unscoped_cnt = unscoped_total = 0
        currency = "CLP"
        for name in unique_names:
            s = stats_by_raw.get(name)
            if not s:
                continue
            scoped_cnt += s["scoped_cnt"]
            scoped_total += s["scoped_total"]
            unscoped_cnt += s["unscoped_cnt"]
            unscoped_total += s["unscoped_total"]
            # Last non-default wins; matches "currency from first tx" loosely.
            currency = s["currency"]

        use_scope = bool(tx_id_uuids) and scoped_cnt > 0
        count = scoped_cnt if use_scope else unscoped_cnt
        total = scoped_total if use_scope else unscoped_total

        # Pick scoped tx list if any scoped rows exist for this canonical, else unscoped.
        # Legacy jobs (no transaction_ids) emit only priority=1 rows in tx_sql, so we
        # must look up priority=1 there even though use_scope is False.
        priority = 1 if (use_scope or not tx_id_uuids) else 2
        bucket: list[dict] = []
        for name in unique_names:
            bucket.extend(tx_by_raw_priority.get((name, priority), []))
        # Sort by real datetime desc (lexicographic sort on "%d-%b-%Y" is wrong).
        _MIN_DT = datetime.min.replace(tzinfo=timezone.utc)
        bucket.sort(key=lambda t: t["_sort_dt"] or _MIN_DT, reverse=True)
        # Strip the internal sort key before returning to caller.
        transactions_info = [{k: v for k, v in t.items() if k != "_sort_dt"} for t in bucket]

        # Currency from first transaction (preserves prior behavior).
        card_currency = transactions_info[0]["currency"] if transactions_info else currency

        cards.append(
            {
                "canonical_merchant_id": str(row.id),
                "display_name": row.display_name,
                "default_category": row.default_category,
                "llm_suggested_categories": canonical_first_suggestion.get(row.id) or [],
                "transactions": transactions_info,
                "transaction_count": count,
                "total_amount": float(total or 0),
                "currency": card_currency,
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
