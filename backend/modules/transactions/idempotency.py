import logging
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from modules.transactions.models import ProcessedWebhook

logger = logging.getLogger(__name__)


async def is_already_processed(db: AsyncSession, message_id: str) -> bool:
    """Return True if this webhook message was already processed (idempotency check).
    Marks it as processed before returning False, so the caller can proceed safely.
    Logs and returns False on DB error to avoid silently dropping webhooks.

    IMPORTANT: the marker is committed BEFORE the caller enqueues the job — if
    the enqueue fails, call ``unmark_processed`` so the provider's redelivery
    isn't answered "duplicate" (which would drop the email forever on Outlook).
    """
    try:
        existing = await db.execute(
            select(ProcessedWebhook).where(ProcessedWebhook.message_id == message_id)
        )
        if existing.scalar_one_or_none():
            return True
        db.add(ProcessedWebhook(message_id=message_id))
        await db.commit()
        return False
    except Exception:
        logger.exception("Failed to check/record webhook idempotency for message_id=%s", message_id)
        return False  # Proceed anyway — better to process twice than to drop


async def unmark_processed(db: AsyncSession, message_id: str) -> None:
    """Roll back the idempotency marker after a failed enqueue so redelivery works."""
    try:
        await db.execute(delete(ProcessedWebhook).where(ProcessedWebhook.message_id == message_id))
        await db.commit()
    except Exception:
        logger.exception("Failed to unmark webhook idempotency for message_id=%s", message_id)
