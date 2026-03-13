from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis.asyncio import Redis
from modules.whatsapp.session import get_session, save_session, clear_session
from modules.whatsapp.sender import send_category_list
from modules.merchants.service import record_category_selection, lookup_merchant
from modules.transactions.models import Transaction, TransactionSplit


async def handle_button_click(phone: str, button_id: str, db: AsyncSession, redis: Redis) -> None:
    """Route a WhatsApp button reply to the correct split action."""
    session = await get_session(phone, redis)
    if not session:
        return  # session expired

    if button_id in ("split_personal", "split_partner"):
        split_type = "personal" if button_id == "split_personal" else "partner"
        await _save_split(session.transaction_id, split_type, None, db)
        await clear_session(phone, redis)

    elif button_id == "split_shared":
        # Advance session to category step
        session.step = "awaiting_category"
        session.split_type = "shared"
        await save_session(phone, session, redis)
        categories = await lookup_merchant(session.raw_merchant, db=db, redis=redis)
        await send_category_list(to=phone, categories=categories)


async def handle_list_selection(
    phone: str, list_item_id: str, list_item_title: str, db: AsyncSession, redis: Redis
) -> None:
    """Route a WhatsApp list selection to category save."""
    session = await get_session(phone, redis)
    if not session:
        return

    category = list_item_title
    await _save_split(session.transaction_id, session.split_type or "shared", category, db)
    await record_category_selection(session.raw_merchant, category, db=db, redis=redis)
    await clear_session(phone, redis)


async def _save_split(
    transaction_id: str, split_type: str, category: str | None, db: AsyncSession
) -> None:
    result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    txn = result.scalar_one_or_none()
    if not txn:
        return
    split = TransactionSplit(
        transaction_id=txn.id,
        split_type=split_type,
        category=category,
        decided_at=datetime.now(timezone.utc),
    )
    db.add(split)
    if category:
        txn.category = category  # denormalize onto transaction
    await db.commit()
