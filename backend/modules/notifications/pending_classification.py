"""Pending shared-card classification nudge — daily cron.

Notifies every active member of a household that has ≥1 shared-card charge
awaiting classification (`needs_classification=True` on a `shared_card`
bank account): "Tienes N cargos por clasificar."

Idempotent per (user, day): guarded by a notification-type + created-at-today
check, so cron retries and manual re-runs never double-send. No notification
when a household's pending count is 0.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.notifications.models import Notification
from modules.notifications.service import create_notification

logger = logging.getLogger(__name__)

PENDING_CLASSIFICATION_TYPE = "pending_card_classification"


async def _notified_today(db: AsyncSession, user_id) -> bool:
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    row = await db.execute(
        select(Notification.id).where(
            Notification.user_id == user_id,
            Notification.type == PENDING_CLASSIFICATION_TYPE,
            Notification.created_at >= today_start,
        )
    )
    return row.first() is not None


async def send_pending_classification_notifications(db: AsyncSession) -> int:
    """Nudge each active member of every household with ≥1 pending
    shared-card charge. Returns the number of notifications created."""
    household_rows = await db.execute(
        text("""
            SELECT DISTINCT ba.household_id
            FROM bank_accounts ba
            JOIN transactions t ON t.bank_account_id = ba.id
            WHERE ba.account_type = 'shared_card'
              AND t.needs_classification IS TRUE
        """)
    )
    household_ids = [r[0] for r in household_rows.all()]
    if not household_ids:
        return 0

    sent = 0
    for household_id in household_ids:
        count_row = await db.execute(
            text("""
                SELECT COUNT(*)
                FROM transactions t
                JOIN bank_accounts ba ON ba.id = t.bank_account_id
                WHERE ba.household_id = :hid
                  AND ba.account_type = 'shared_card'
                  AND t.needs_classification IS TRUE
            """),
            {"hid": str(household_id)},
        )
        count = count_row.scalar_one()
        if count <= 0:
            continue

        member_rows = await db.execute(
            text("""
                SELECT user_id FROM household_members
                WHERE household_id = :hid AND left_at IS NULL
            """),
            {"hid": str(household_id)},
        )
        member_ids = [r[0] for r in member_rows.all()]

        for user_id in member_ids:
            if await _notified_today(db, user_id):
                continue
            await create_notification(
                db,
                user_id,
                type=PENDING_CLASSIFICATION_TYPE,
                title=f"Tienes {count} cargos por clasificar",
                payload={"count": count, "household_id": str(household_id)},
            )
            sent += 1

    logger.info("send_pending_classification_notifications: sent %d notifications", sent)
    return sent
