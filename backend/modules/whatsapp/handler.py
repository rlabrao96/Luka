from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis.asyncio import Redis
from modules.whatsapp.session import (
    get_session,
    save_session,
    clear_session,
    save_msgid,
    get_transaction_id_by_msgid,
)
from modules.whatsapp.sender import send_category_list, send_text
from modules.merchants.service import record_category_selection, lookup_merchant
from modules.transactions.models import Transaction, TransactionSplit


async def handle_button_click(
    phone: str, button_id: str, context_msg_id: str, db: AsyncSession, redis: Redis
) -> None:
    """Route a WhatsApp button reply to the correct split action."""
    transaction_id = await get_transaction_id_by_msgid(context_msg_id, redis)
    if not transaction_id:
        return  # message too old or unknown

    session = await get_session(phone, transaction_id, redis)
    if not session:
        return  # session expired

    if button_id == "transaction_error":
        await send_text(to=phone, body="🔧 Esta funcionalidad estará disponible pronto.")
        return

    if button_id in ("split_personal", "split_shared"):
        split_type = {
            "split_personal": "personal",
            "split_shared": "shared",
        }[button_id]
        session.step = "awaiting_category"
        session.split_type = split_type
        await save_session(phone, session, redis)
        categories = await lookup_merchant(session.raw_merchant, db=db, redis=redis)
        category_wamid = await send_category_list(to=phone, categories=categories)
        await save_msgid(category_wamid, transaction_id, redis)


async def handle_list_selection(
    phone: str,
    list_item_id: str,
    list_item_title: str,
    context_msg_id: str,
    db: AsyncSession,
    redis: Redis,
) -> None:
    """Route a WhatsApp list selection to category save."""
    transaction_id = await get_transaction_id_by_msgid(context_msg_id, redis)
    if not transaction_id:
        return

    session = await get_session(phone, transaction_id, redis)
    if not session:
        return

    category = list_item_title
    await _save_split(session.transaction_id, session.split_type or "shared", category, db)
    await record_category_selection(session.raw_merchant, category, db=db, redis=redis)
    await clear_session(phone, transaction_id, redis)
    await send_text(to=phone, body=f"✅ Guardado: {session.raw_merchant} → {category}")


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
        txn.category = category
    await db.commit()
