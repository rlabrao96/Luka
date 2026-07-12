"""Recurring-charge guardian (P8).

Two watchers over the detected-subscriptions cache:

1. Price-increase alerts — fired when a subscription's latest charge rose
   ≥5% (and ≥ one whole major unit) vs the previous charge. Runs inside the
   detection refresh so it sees old-vs-new state exactly once per change.
2. Pre-charge heads-up — daily cron: "Netflix te cobrará ~$12.990 pasado
   mañana". Predicted from `next_charge_day` of each active subscription.

Both are idempotent via Notification payload keys (merchant + amount /
merchant + month), so cron retries never double-notify.
"""

from __future__ import annotations

import calendar
import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.currencies.units import format_major, minor_units_per_major
from modules.notifications.models import Notification
from modules.notifications.service import create_notification

logger = logging.getLogger(__name__)

PRICE_INCREASE_TYPE = "subscription_price_increase"
UPCOMING_CHARGE_TYPE = "subscription_upcoming_charge"

_INCREASE_THRESHOLD_PCT = 5.0


async def _notification_exists(
    db: AsyncSession, user_id, type_: str, key_field: str, key_value: str
) -> bool:
    row = await db.execute(
        select(Notification.id).where(
            Notification.user_id == user_id,
            Notification.type == type_,
            Notification.payload[key_field].astext == key_value,
        )
    )
    return row.first() is not None


async def emit_price_increase_alerts(
    db: AsyncSession, user_id, old_items: list[dict], new_items: list[dict]
) -> int:
    """Compare refreshed detections against the previous cache snapshot."""
    old_by_key = {i.get("merchant_name"): i for i in old_items if isinstance(i, dict)}
    sent = 0
    for item in new_items:
        merchant = item.get("merchant_name")
        if not merchant or item.get("status") != "active":
            continue
        try:
            last = Decimal(str(item.get("last_amount") or 0))
            prev_item = old_by_key.get(merchant) or {}
            prev = Decimal(str(prev_item.get("last_amount") or 0))
        except Exception:
            continue
        if prev <= 0 or last <= prev:
            continue
        pct = float((last - prev) / prev * 100)
        currency = item.get("currency") or "CLP"
        # Ignore sub-threshold noise and sub-one-major-unit jitter.
        if pct < _INCREASE_THRESHOLD_PCT or (last - prev) < minor_units_per_major(currency):
            continue
        dedup_key = f"{merchant}:{last}"
        if await _notification_exists(db, user_id, PRICE_INCREASE_TYPE, "key", dedup_key):
            continue
        title = (
            f"📈 {merchant} subió de {format_major(prev, currency)} "
            f"a {format_major(last, currency)} (+{round(pct)}%)"
        )
        await create_notification(
            db,
            user_id,
            type=PRICE_INCREASE_TYPE,
            title=title,
            payload={
                "key": dedup_key,
                "merchant": merchant,
                "previous_amount": str(prev),
                "new_amount": str(last),
                "pct": round(pct, 1),
                "currency": currency,
            },
        )
        sent += 1
    return sent


def _next_charge_date(next_charge_day: int, today: date) -> date:
    """Next occurrence of `next_charge_day`, clamped to month length."""
    day = max(1, min(int(next_charge_day or 1), 28 if next_charge_day is None else 31))

    def clamp(year: int, month: int) -> date:
        return date(year, month, min(day, calendar.monthrange(year, month)[1]))

    this_month = clamp(today.year, today.month)
    if this_month >= today:
        return this_month
    if today.month == 12:
        return clamp(today.year + 1, 1)
    return clamp(today.year, today.month + 1)


async def send_precharge_alerts_for_user(db: AsyncSession, user_id: str) -> int:
    """Heads-up for active subscriptions charging within the next 2 days."""
    row = await db.execute(
        text("SELECT result_json FROM detected_subscriptions_cache WHERE user_id = :uid"),
        {"uid": str(user_id)},
    )
    items = row.scalar_one_or_none()
    if not isinstance(items, list):
        return 0

    today = date.today()
    horizon = today + timedelta(days=2)
    sent = 0
    for item in items:
        if not isinstance(item, dict) or item.get("status") != "active":
            continue
        merchant = item.get("merchant_name")
        ncd = item.get("next_charge_day")
        if not merchant or not ncd:
            continue
        charge_date = _next_charge_date(int(ncd), today)
        if not (today < charge_date <= horizon):
            continue
        month_key = charge_date.strftime("%Y-%m")
        dedup_key = f"{merchant}:{month_key}"
        if await _notification_exists(
            db, uuid.UUID(user_id), UPCOMING_CHARGE_TYPE, "key", dedup_key
        ):
            continue
        currency = item.get("currency") or "CLP"
        amount = Decimal(str(item.get("last_amount") or 0))
        when = "mañana" if charge_date == today + timedelta(days=1) else "pasado mañana"
        title = f"🔔 {merchant} te cobrará ~{format_major(amount, currency)} {when}"
        await create_notification(
            db,
            uuid.UUID(user_id),
            type=UPCOMING_CHARGE_TYPE,
            title=title,
            payload={
                "key": dedup_key,
                "merchant": merchant,
                "expected_amount": str(amount),
                "currency": currency,
                "charge_date": charge_date.isoformat(),
            },
        )
        sent += 1
    return sent
