from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis.asyncio import Redis
from modules.whatsapp.session import get_session, save_session, clear_session
from modules.whatsapp.sender import send_category_list, send_text
from modules.merchants.service import record_category_selection, lookup_merchant
from modules.transactions.models import Transaction, TransactionSplit


def _parse_id(interactive_id: str) -> tuple[str, str]:
    """Parse 'action:txn-uuid' → ('action', 'txn-uuid').

    Button IDs look like 'split_personal:abc-123'.
    Category list IDs look like 'cat_0:abc-123'.
    Legacy IDs without ':' return ('action', '').
    """
    parts = interactive_id.split(":", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else (interactive_id, "")


async def handle_button_click(phone: str, button_id: str, db: AsyncSession, redis: Redis) -> None:
    """Route a WhatsApp button reply to the correct split action."""
    action, txn_id = _parse_id(button_id)

    session = await get_session(phone, txn_id, redis) if txn_id else None
    if not session:
        return  # session expired or missing

    if action in ("split_personal", "split_partner", "split_shared"):
        split_type = {
            "split_personal": "personal",
            "split_partner": "partner",
            "split_shared": "shared",
        }[action]
        # Save split type, then advance to category step
        session.step = "awaiting_category"
        session.split_type = split_type
        await save_session(phone, session, redis)
        categories = await lookup_merchant(session.raw_merchant, db=db, redis=redis)
        await send_category_list(
            to=phone, categories=categories, transaction_id=session.transaction_id
        )


async def handle_list_selection(
    phone: str, list_item_id: str, list_item_title: str, db: AsyncSession, redis: Redis
) -> None:
    """Route a WhatsApp list selection to category save."""
    _, txn_id = _parse_id(list_item_id)

    session = await get_session(phone, txn_id, redis) if txn_id else None
    if not session:
        return

    category = list_item_title
    await _save_split(session.transaction_id, session.split_type or "shared", category, db)
    await record_category_selection(session.raw_merchant, category, db=db, redis=redis)
    await clear_session(phone, txn_id, redis)
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
        txn.category = category  # denormalize onto transaction
    await db.commit()
