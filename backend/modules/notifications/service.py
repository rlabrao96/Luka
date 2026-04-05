import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from modules.notifications.models import Notification


async def get_user_notifications(db: AsyncSession, user_id: uuid.UUID) -> list[Notification]:
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
    )
    return list(result.scalars().all())


async def get_unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.status == "unread")
    )
    return result.scalar_one()


async def update_notification(
    db: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID, status: str
) -> Notification | None:
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        return None

    notif.status = status
    notif.updated_at = datetime.now(timezone.utc)
    if status == "read":
        notif.read_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(notif)
    return notif


async def delete_notification(
    db: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID
) -> bool:
    from modules.merchant_review.models import MerchantReviewJob

    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        return False

    # Unlink any review jobs referencing this notification
    await db.execute(
        MerchantReviewJob.__table__.update()
        .where(MerchantReviewJob.notification_id == notification_id)
        .values(notification_id=None)
    )

    await db.delete(notif)
    await db.commit()
    return True


async def create_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    type: str,
    title: str,
    payload: dict | None = None,
) -> Notification:
    notif = Notification(
        user_id=user_id,
        type=type,
        title=title,
        payload=payload,
    )
    db.add(notif)
    await db.commit()
    await db.refresh(notif)
    return notif
