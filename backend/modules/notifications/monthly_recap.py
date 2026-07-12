"""Monthly recap ("Tu mes en Luka") — computed per user on the 1st of month.

Summarizes the PREVIOUS month: total spend vs the month before, top category
movers, and a settlement reminder when the household has an outstanding
suggestion. Delivered as an in-app notification and (when verified) a
WhatsApp message.

Idempotent per (user, month): guarded by a notification-type + payload month
check, so cron retries and manual re-runs never double-send.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.auth.models import User
from modules.currencies.units import format_major
from modules.notifications.models import Notification
from modules.notifications.service import create_notification
from modules.transactions.totals import totals_exclusion_sql

logger = logging.getLogger(__name__)

RECAP_TYPE = "monthly_recap"


def _prev_month(anchor: date) -> date:
    return (
        date(anchor.year - 1, 12, 1)
        if anchor.month == 1
        else date(anchor.year, anchor.month - 1, 1)
    )


async def _category_totals(
    db: AsyncSession, user_id: uuid.UUID, month: date, currency: str
) -> dict[str, int]:
    rows = await db.execute(
        text(f"""
            SELECT COALESCE(t.category, 'Sin categoría') AS category,
                   COALESCE(SUM(ABS(t.amount)), 0) AS total
            FROM transactions t
            WHERE t.user_id = :uid
              AND t.currency = :ccy
              AND t.transaction_type = 'expense'
              AND {totals_exclusion_sql("t")}
              AND DATE_TRUNC('month', t.transaction_date::DATE) = CAST(:month_start AS DATE)
            GROUP BY 1
        """),
        {"uid": str(user_id), "ccy": currency, "month_start": month},
    )
    return {r[0]: int(r[1]) for r in rows}


async def already_sent(db: AsyncSession, user_id: uuid.UUID, month_key: str) -> bool:
    row = await db.execute(
        select(Notification.id).where(
            Notification.user_id == user_id,
            Notification.type == RECAP_TYPE,
            Notification.payload["month"].astext == month_key,
        )
    )
    return row.first() is not None


def build_recap_text(
    *,
    month_label: str,
    currency: str,
    total: int,
    prev_total: int,
    movers: list[tuple[str, int]],
    settlement_line: str | None,
) -> str:
    lines = [f"📊 Tu mes en Luka — {month_label}"]
    lines.append(f"Gastaste {format_major(total, currency)}.")
    if prev_total > 0:
        delta_pct = round((total - prev_total) / prev_total * 100)
        if delta_pct <= -3:
            lines.append(f"👏 {abs(delta_pct)}% menos que el mes anterior.")
        elif delta_pct >= 3:
            lines.append(f"⚠️ {delta_pct}% más que el mes anterior.")
        else:
            lines.append("Al mismo ritmo que el mes anterior.")
    if movers:
        lines.append("Lo que más cambió:")
        for cat, delta in movers:
            arrow = "▲" if delta > 0 else "▼"
            lines.append(f"  {arrow} {cat}: {format_major(abs(delta), currency)}")
    if settlement_line:
        lines.append(settlement_line)
    lines.append("Revisa el detalle en Luka 📱")
    return "\n".join(lines)


async def send_monthly_recap_for_user(db: AsyncSession, user_id: str) -> bool:
    """Compute + deliver the recap for one user. Returns True when sent."""
    user = (
        await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    ).scalar_one_or_none()
    if user is None:
        return False

    today = date.today()
    recap_month = _prev_month(date(today.year, today.month, 1))
    month_key = recap_month.strftime("%Y-%m")
    if await already_sent(db, user.id, month_key):
        return False

    currency = user.preferred_currency or "CLP"
    totals = await _category_totals(db, user.id, recap_month, currency)
    total = sum(totals.values())
    if total <= 0:
        return False  # nothing to recap — stay silent, don't spam

    prev_totals = await _category_totals(db, user.id, _prev_month(recap_month), currency)
    prev_total = sum(prev_totals.values())

    deltas = [
        (cat, totals.get(cat, 0) - prev_totals.get(cat, 0))
        for cat in set(totals) | set(prev_totals)
    ]
    movers = sorted((d for d in deltas if abs(d[1]) > 0), key=lambda kv: abs(kv[1]), reverse=True)[
        :3
    ]

    # Settlement reminder (best effort — never blocks the recap).
    settlement_line = None
    try:
        hh_row = await db.execute(
            text(
                "SELECT household_id FROM household_members "
                "WHERE user_id = :uid AND left_at IS NULL LIMIT 1"
            ),
            {"uid": str(user.id)},
        )
        hh = hh_row.scalar_one_or_none()
        if hh:
            from modules.households.service import get_settlement

            settlement = await get_settlement(db, hh, month=month_key, currency=currency)
            for t in settlement.get("transfers", []):
                if str(t.get("from_user_id")) == str(user.id):
                    settlement_line = (
                        f"💸 Pendiente: le debes {format_major(int(t['amount']), currency)} "
                        f"a {t['to_user_name']} por {recap_month.strftime('%B')}."
                    )
                    break
    except Exception:
        logger.warning("recap settlement lookup failed for %s", user_id, exc_info=True)

    month_label = recap_month.strftime("%B %Y").capitalize()
    body = build_recap_text(
        month_label=month_label,
        currency=currency,
        total=total,
        prev_total=prev_total,
        movers=movers,
        settlement_line=settlement_line,
    )

    await create_notification(
        db,
        user.id,
        type=RECAP_TYPE,
        title=f"Tu mes en Luka — {month_label}",
        payload={
            "month": month_key,
            "currency": currency,
            "total": total,
            "prev_total": prev_total,
            "movers": [{"category": c, "delta": d} for c, d in movers],
            "body": body,
        },
    )

    if user.whatsapp_verified and user.phone_whatsapp:
        try:
            from modules.whatsapp.sender import send_text

            await send_text(to=user.phone_whatsapp, body=body)
        except Exception:
            logger.warning("recap WhatsApp send failed for %s", user_id, exc_info=True)

    return True
