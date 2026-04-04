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
    save_active_edit,
    get_active_edit_transaction_id,
    clear_active_edit,
)
from modules.whatsapp.sender import send_category_list, send_text, send_edit_options, send_expense_alert
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
        transaction_id = await get_transaction_id_by_msgid(context_msg_id, redis)
        if not transaction_id:
            return
        edit_wamid = await send_edit_options(to=phone)
        await save_msgid(edit_wamid, transaction_id, redis)
        return

    if button_id in ("edit_merchant", "edit_amount"):
        transaction_id = await get_transaction_id_by_msgid(context_msg_id, redis)
        if not transaction_id:
            return
        session = await get_session(phone, transaction_id, redis)
        if not session:
            return
        if button_id == "edit_merchant":
            session.step = "awaiting_new_merchant"
            await save_session(phone, session, redis)
            await save_active_edit(phone, transaction_id, redis)
            await send_text(to=phone, body="Escribe el nombre del comercio:")
        else:
            session.step = "awaiting_new_amount"
            await save_session(phone, session, redis)
            await save_active_edit(phone, transaction_id, redis)
            await send_text(to=phone, body="Escribe el monto en CLP (solo números):")
        return

    if button_id in ("split_personal", "split_shared"):
        split_type = {
            "split_personal": "personal",
            "split_shared": "shared",
        }[button_id]
        session.step = "awaiting_category"
        session.split_type = split_type
        await save_session(phone, session, redis)
        txn_result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
        txn = txn_result.scalar_one_or_none()
        amount_str = f"${txn.amount:,}" if txn else session.raw_merchant
        categories = await lookup_merchant(session.raw_merchant, db=db, redis=redis)
        if not categories:
            categories = [
                "Supermercado", "Alimentación", "Restaurantes", "Transporte",
                "Combustible", "Salud", "Hogar", "Entretenimiento", "Ropa", "Otros",
            ]
        context_msg = f"¿A qué categoría pertenece el gasto de {amount_str} en {session.raw_merchant}?"
        category_wamid = await send_category_list(to=phone, categories=categories, context_msg=context_msg)
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
    split_label = {"personal": "Personal", "shared": "Compartido"}.get(session.split_type or "shared", session.split_type)
    await send_text(to=phone, body=f"✅ Guardado: {session.raw_merchant} → {category} ({split_label})")


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


async def handle_text_message(
    phone: str, text: str, db: AsyncSession, redis: Redis
) -> None:
    """Handle a free-text reply during an active edit step."""
    transaction_id = await get_active_edit_transaction_id(phone, redis)
    if not transaction_id:
        return  # no active edit — ignore

    session = await get_session(phone, transaction_id, redis)
    if not session:
        await clear_active_edit(phone, redis)
        return

    txn_result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    txn = txn_result.scalar_one_or_none()
    if not txn:
        await clear_active_edit(phone, redis)
        return

    if session.step == "awaiting_new_merchant":
        txn.raw_merchant_name = text.strip()
        session.raw_merchant = text.strip()
    elif session.step == "awaiting_new_amount":
        cleaned = text.strip().replace(".", "").replace(",", "").replace("$", "")
        if not cleaned.isdigit():
            await send_text(to=phone, body="❌ Por favor escribe solo el número (ej: 15990).")
            return
        txn.amount = int(cleaned)
    else:
        return  # unexpected step

    await db.commit()
    await clear_active_edit(phone, redis)

    # Determine is_joint from bank account type
    is_joint = False
    if txn.bank_account_id:
        from modules.households.models import BankAccount
        acct_result = await db.execute(select(BankAccount).where(BankAccount.id == txn.bank_account_id))
        acct = acct_result.scalar_one_or_none()
        is_joint = acct.account_type == "joint" if acct else False

    # Re-send the expense alert with updated data
    categories = await lookup_merchant(txn.raw_merchant_name, db=db, redis=redis)
    new_msg_id = await send_expense_alert(
        to=phone,
        amount=txn.amount,
        merchant=txn.raw_merchant_name,
        partner_name="tu pareja",
        is_joint=is_joint,
        categories=categories,
        currency=txn.currency or "CLP",
    )
    # Reset session step for the new message
    session.step = "awaiting_category" if is_joint else "awaiting_split"
    await save_session(phone, session, redis)
    await save_msgid(new_msg_id, transaction_id, redis)
