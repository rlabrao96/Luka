from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date
from decimal import Decimal

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def predict_next_date(last_date: date) -> date:
    """Project day-of-month to next calendar month, clamping to month end."""
    year = last_date.year
    month = last_date.month + 1
    if month > 12:
        month = 1
        year += 1
    max_day = calendar.monthrange(year, month)[1]
    day = min(last_date.day, max_day)
    return date(year, month, day)


def _are_consecutive(months: list[str]) -> int:
    """Returns length of longest consecutive run from the most recent month backwards."""
    if len(months) < 2:
        return len(months)

    sorted_months = sorted(months, reverse=True)
    run = 1
    for i in range(len(sorted_months) - 1):
        y1, m1 = map(int, sorted_months[i].split("-"))
        y2, m2 = map(int, sorted_months[i + 1].split("-"))
        expected_month = m1 - 1 if m1 > 1 else 12
        expected_year = y1 if m1 > 1 else y1 - 1
        if y2 == expected_year and m2 == expected_month:
            run += 1
        else:
            break
    return run


def _within_tolerance(amounts: list[Decimal], tolerance: float = 0.20) -> bool:
    """Check if all amounts are within tolerance of the median."""
    if len(amounts) < 2:
        return True
    median = sorted(amounts)[len(amounts) // 2]
    if median == 0:
        return False
    return all(abs(float(a - median) / float(median)) <= tolerance for a in amounts)


def detect_from_rows(rows: list[dict]) -> list[dict]:
    """Pure function: given transaction rows, detect recurring patterns."""
    merchants: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        merchants[row["merchant_key"]].append(row)

    results = []
    for merchant_key, txns in merchants.items():
        months = list({t["month"] for t in txns})
        consecutive = _are_consecutive(months)
        if consecutive < 2:
            continue

        amounts = [t["amount"] for t in txns]
        if not _within_tolerance(amounts):
            continue

        sorted_txns = sorted(txns, key=lambda t: t["tx_date"], reverse=True)
        # Ensure tx_date is a plain date (DB may return datetime with tz)
        for t in sorted_txns:
            if hasattr(t["tx_date"], "date"):
                t["tx_date"] = t["tx_date"].date()
        latest = sorted_txns[0]
        previous = sorted_txns[1] if len(sorted_txns) > 1 else None

        avg_amount = sum(amounts) / len(amounts)
        last_amount = latest["amount"]
        previous_amount = previous["amount"] if previous else None

        if previous_amount and previous_amount != 0:
            change_pct = round(
                float(last_amount - previous_amount) / float(previous_amount) * 100, 1
            )
            if abs(change_pct) < 1:
                trend = "stable"
            elif change_pct > 0:
                trend = "increased"
            else:
                trend = "decreased"
        else:
            trend = "stable"
            change_pct = None

        # Build recent charges (last 3 transactions)
        recent_charges = [{"date": t["tx_date"], "amount": t["amount"]} for t in sorted_txns[:3]]

        results.append(
            {
                "merchant_name": merchant_key,
                "category": latest["category"],
                "average_amount": round(avg_amount, 0),
                "last_amount": last_amount,
                "previous_amount": previous_amount,
                "last_charge_date": latest["tx_date"],
                "next_charge_day": latest["tx_date"].day,
                "frequency": "monthly",
                "trend": trend,
                "trend_pct": change_pct,
                "months_seen": consecutive,
                "split_type": latest["split_type"],
                "currency": latest.get("currency", "CLP"),
                "status": "active",
                "recent_charges": recent_charges,
            }
        )

    results.sort(key=lambda r: r["last_amount"], reverse=True)
    return results


async def get_detected_subscriptions(db: AsyncSession, user_id, months_back: int = 6) -> dict:
    """Read from DB cache, compute on first access. Merge overrides at read time."""
    # Check DB cache
    cache_row = await db.execute(
        text(
            "SELECT result_json, computed_at FROM detected_subscriptions_cache WHERE user_id = :uid"
        ),
        {"uid": str(user_id)},
    )
    row = cache_row.first()

    if row:
        raw_items = row.result_json if isinstance(row.result_json, list) else row.result_json
        computed_at = row.computed_at
    else:
        # First access — compute and store
        raw_items, computed_at = await _compute_and_store(db, user_id, months_back)

    # Merge overrides
    items = await _merge_overrides(db, user_id, raw_items)

    # Filter out dismissed items
    visible_items = [i for i in items if i.get("status") != "dismissed"]

    # Compute summary per currency (only active items)
    summary_by_currency = await _compute_summary_by_currency(db, user_id, visible_items)

    return {
        "items": visible_items,
        "summary_by_currency": summary_by_currency,
        "computed_at": computed_at,
    }


async def refresh_subscriptions(db: AsyncSession, user_id, months_back: int = 6) -> dict:
    """Force recompute and return fresh data."""
    await _compute_and_store(db, user_id, months_back)
    return await get_detected_subscriptions(db, user_id, months_back)


async def upsert_override(
    db: AsyncSession,
    user_id,
    merchant_key: str,
    status: str | None,
    category: str | None,
    next_charge_day: int | None,
) -> None:
    """Create or update a subscription override."""
    await db.execute(
        text("""
            INSERT INTO subscription_overrides (user_id, merchant_key, status, category, next_charge_day, updated_at)
            VALUES (:uid, :mk, COALESCE(:status, 'active'), :cat, :day, NOW())
            ON CONFLICT (user_id, merchant_key)
            DO UPDATE SET
                status = COALESCE(:status, subscription_overrides.status),
                category = CASE WHEN :cat IS NOT NULL THEN :cat ELSE subscription_overrides.category END,
                next_charge_day = CASE WHEN :day IS NOT NULL THEN :day ELSE subscription_overrides.next_charge_day END,
                updated_at = NOW()
        """),
        {
            "uid": str(user_id),
            "mk": merchant_key,
            "status": status,
            "cat": category,
            "day": next_charge_day,
        },
    )
    await db.commit()


async def _compute_and_store(
    db: AsyncSession, user_id, months_back: int = 6
) -> tuple[list[dict], object]:
    """Heavy computation: query transactions, detect patterns, store in DB cache."""
    sql = text("""
        SELECT
            COALESCE(m.normalized_name, t.raw_merchant_name) AS merchant_key,
            t.category,
            ABS(t.amount) AS amount,
            t.transaction_date AS tx_date,
            TO_CHAR(t.transaction_date, 'YYYY-MM') AS month,
            COALESCE(ts.split_type, 'personal') AS split_type,
            t.currency
        FROM transactions t
        LEFT JOIN merchants m ON m.id = t.merchant_id
        LEFT JOIN transaction_splits ts ON ts.transaction_id = t.id
        WHERE t.user_id = :user_id
          AND t.transaction_type = 'expense'
          AND t.transaction_date >= (NOW() - :months_back * INTERVAL '1 month')::DATE
        ORDER BY t.transaction_date DESC
    """)
    result = await db.execute(sql, {"user_id": str(user_id), "months_back": months_back})
    rows = [dict(r._mapping) for r in result.all()]
    items = detect_from_rows(rows)

    # Upsert into DB cache (store raw items, before override merging)
    import json

    items_json = json.dumps(items, default=str)
    await db.execute(
        text("""
            INSERT INTO detected_subscriptions_cache (user_id, result_json, computed_at)
            VALUES (:uid, :data::jsonb, NOW())
            ON CONFLICT (user_id)
            DO UPDATE SET result_json = :data::jsonb, computed_at = NOW()
        """),
        {"uid": str(user_id), "data": items_json},
    )
    await db.commit()

    # Get the computed_at timestamp
    ts_row = await db.execute(
        text("SELECT computed_at FROM detected_subscriptions_cache WHERE user_id = :uid"),
        {"uid": str(user_id)},
    )
    computed_at = ts_row.scalar()

    return items, computed_at


async def _merge_overrides(db: AsyncSession, user_id, raw_items: list[dict]) -> list[dict]:
    """Apply subscription_overrides on top of raw detected items."""
    result = await db.execute(
        text(
            "SELECT merchant_key, status, category, next_charge_day FROM subscription_overrides WHERE user_id = :uid"
        ),
        {"uid": str(user_id)},
    )
    overrides = {row.merchant_key: row for row in result.all()}

    merged = []
    for item in raw_items:
        item = dict(item)  # copy
        override = overrides.get(item["merchant_name"])
        if override:
            item["status"] = override.status
            if override.category:
                item["category"] = override.category
            if override.next_charge_day:
                item["next_charge_day"] = override.next_charge_day
        merged.append(item)
    return merged


async def _compute_summary_by_currency(db: AsyncSession, user_id, active_items: list[dict]) -> dict:
    """Compute SubscriptionsSummary per currency."""
    from collections import defaultdict
    from decimal import Decimal

    by_currency: dict[str, list[dict]] = defaultdict(list)
    for item in active_items:
        if item.get("status") == "active":
            by_currency[item.get("currency", "CLP")].append(item)

    summary = {}
    for currency, items in by_currency.items():
        total_recurring = sum(Decimal(str(i["last_amount"])) for i in items)

        # Get total monthly expenses for this currency
        monthly_total_sql = text("""
            SELECT COALESCE(SUM(ABS(t.amount)), 0) AS total
            FROM transactions t
            WHERE t.user_id = :user_id
              AND t.transaction_type = 'expense'
              AND t.currency = :currency
              AND DATE_TRUNC('month', t.transaction_date::DATE) = DATE_TRUNC('month', NOW()::DATE)
        """)
        monthly_result = await db.execute(
            monthly_total_sql, {"user_id": str(user_id), "currency": currency}
        )
        monthly_total = monthly_result.scalar() or Decimal("0")

        pct_of_total = (
            round(float(total_recurring) / float(monthly_total) * 100, 1)
            if monthly_total > 0
            else 0
        )

        summary[currency] = {
            "total_recurring": total_recurring,
            "monthly_total": monthly_total,
            "pct_of_total": pct_of_total,
            "count": len(items),
        }

    return summary


async def invalidate_subscriptions_cache(user_id) -> None:
    """Legacy: kept for backward compat. Will clean up old Redis keys."""
    from core.cache import cache_delete

    await cache_delete(f"subscriptions:v2:{user_id}")
