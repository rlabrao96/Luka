"""Recurring-charge guardian (P8): price increases + pre-charge heads-up."""

from __future__ import annotations

import json
from datetime import date, timedelta

import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.notifications.models import Notification
from modules.subscriptions.guardian import (
    _next_charge_date,
    emit_price_increase_alerts,
    send_precharge_alerts_for_user,
)
from sqlalchemy import select, text


def _item(merchant, last_amount, currency="CLP", next_charge_day=None, status="active"):
    return {
        "merchant_name": merchant,
        "last_amount": last_amount,
        "currency": currency,
        "next_charge_day": next_charge_day,
        "status": status,
    }


async def _notifs(db, user_id, type_):
    return (
        (
            await db.execute(
                select(Notification).where(
                    Notification.user_id == user_id, Notification.type == type_
                )
            )
        )
        .scalars()
        .all()
    )


async def test_price_increase_alert_fires_once(db, make_user):
    user = await make_user()
    old = [_item("Netflix", 10990)]
    new = [_item("Netflix", 12990)]

    assert await emit_price_increase_alerts(db, user.id, old, new) == 1
    notifs = await _notifs(db, user.id, "subscription_price_increase")
    assert len(notifs) == 1
    assert "Netflix" in notifs[0].title
    assert notifs[0].payload["pct"] > 5

    # Same increase again → idempotent.
    assert await emit_price_increase_alerts(db, user.id, old, new) == 0


async def test_price_increase_ignores_noise(db, make_user):
    user = await make_user()
    # +1.8% → below threshold.
    assert (
        await emit_price_increase_alerts(
            db, user.id, [_item("Spotify", 11000)], [_item("Spotify", 11200)]
        )
        == 0
    )
    # Decrease → never alerts.
    assert (
        await emit_price_increase_alerts(
            db, user.id, [_item("Spotify", 11000)], [_item("Spotify", 9000)]
        )
        == 0
    )


async def test_precharge_alert_within_horizon(db, make_user):
    user = await make_user()
    charge_day = (date.today() + timedelta(days=2)).day
    items = [_item("HBO Max", 9990, next_charge_day=charge_day)]
    await db.execute(
        text(
            "INSERT INTO detected_subscriptions_cache (user_id, result_json, computed_at) "
            "VALUES (:uid, CAST(:data AS jsonb), NOW())"
        ),
        {"uid": str(user.id), "data": json.dumps(items)},
    )
    await db.flush()

    assert await send_precharge_alerts_for_user(db, str(user.id)) == 1
    notifs = await _notifs(db, user.id, "subscription_upcoming_charge")
    assert len(notifs) == 1
    assert "HBO Max" in notifs[0].title

    # Re-run same day → idempotent.
    assert await send_precharge_alerts_for_user(db, str(user.id)) == 0


def test_next_charge_date_clamps_short_months():
    # Day 31 in a 30-day month clamps to the 30th.
    assert _next_charge_date(31, date(2026, 4, 10)) == date(2026, 4, 30)
    # Already passed this month → next month.
    assert _next_charge_date(5, date(2026, 4, 10)) == date(2026, 5, 5)
