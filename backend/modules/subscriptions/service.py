from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date
from decimal import Decimal

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import cache_get, cache_set, cache_delete

logger = logging.getLogger(__name__)

CACHE_TTL = 3 * 24 * 3600  # 3 days


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

        results.append(
            {
                "merchant_name": merchant_key,
                "category": latest["category"],
                "average_amount": round(avg_amount, 0),
                "last_amount": last_amount,
                "previous_amount": previous_amount,
                "last_charge_date": latest["tx_date"],
                "predicted_next_date": predict_next_date(latest["tx_date"]),
                "frequency": "monthly",
                "trend": trend,
                "trend_pct": change_pct,
                "months_seen": consecutive,
                "split_type": latest["split_type"],
            }
        )

    results.sort(key=lambda r: r["last_amount"], reverse=True)
    return results


def _cache_key(user_id) -> str:
    return f"subscriptions:{user_id}"


async def get_detected_subscriptions(db: AsyncSession, user_id, months_back: int = 6) -> dict:
    """Return cached subscriptions, or compute and cache if miss."""
    cached = await cache_get(_cache_key(user_id))
    if cached:
        return cached

    return await _compute_and_cache(db, user_id, months_back)


async def invalidate_subscriptions_cache(user_id) -> None:
    """Call this when new transactions arrive (webhook, sync) to bust the cache."""
    await cache_delete(_cache_key(user_id))


async def _compute_and_cache(db: AsyncSession, user_id, months_back: int = 6) -> dict:
    """Heavy computation: query transactions, detect patterns, cache result."""
    sql = text("""
        SELECT
            COALESCE(m.normalized_name, t.raw_merchant_name) AS merchant_key,
            t.category,
            ABS(t.amount) AS amount,
            t.transaction_date AS tx_date,
            TO_CHAR(t.transaction_date, 'YYYY-MM') AS month,
            COALESCE(ts.split_type, 'personal') AS split_type
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

    # Calculate summary in backend so frontend doesn't need all transactions
    total_recurring = sum(i["last_amount"] for i in items)

    monthly_total_sql = text("""
        SELECT COALESCE(SUM(ABS(t.amount)), 0) AS total
        FROM transactions t
        WHERE t.user_id = :user_id
          AND t.transaction_type = 'expense'
          AND DATE_TRUNC('month', t.transaction_date::DATE) = DATE_TRUNC('month', NOW()::DATE)
    """)
    monthly_result = await db.execute(monthly_total_sql, {"user_id": str(user_id)})
    monthly_total = monthly_result.scalar() or Decimal("0")

    pct_of_total = (
        round(float(total_recurring) / float(monthly_total) * 100, 1) if monthly_total > 0 else 0
    )

    result = {
        "items": items,
        "summary": {
            "total_recurring": total_recurring,
            "monthly_total": monthly_total,
            "pct_of_total": pct_of_total,
            "count": len(items),
        },
    }
    await cache_set(_cache_key(user_id), result, CACHE_TTL)
    return result
