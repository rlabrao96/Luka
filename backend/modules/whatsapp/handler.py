import re
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from redis.asyncio import Redis
from modules.whatsapp.session import (
    WhatsAppSession,
    get_session,
    save_session,
    clear_session,
    save_msgid,
    get_transaction_id_by_msgid,
    save_active_edit,
    get_active_edit_transaction_id,
    clear_active_edit,
    _normalize_phone,
)
from modules.whatsapp.sender import send_category_list, send_text, send_edit_options, send_expense_alert
from modules.merchants.service import record_category_selection, get_user_ranked_categories
from modules.transactions.models import Transaction, TransactionSplit

_OTRAS = "Otras categorías"


def _paginate_categories(ranked: list[str]) -> tuple[list[str], list[str]]:
    """Split a ranked list into (display_page, overflow).
    display_page has up to 9 items; if overflow exists, _OTRAS is appended as item 10.
    """
    if len(ranked) <= 9:
        return ranked, []
    return ranked[:9] + [_OTRAS], ranked[9:]


def parse_manual_expense(text: str) -> tuple[int, str] | None:
    """Parse 'gasto 5000 Starbucks' or '5000 Starbucks' → (5000, 'Starbucks').

    Returns None if the text cannot be interpreted as a manual expense.
    """
    text = re.sub(r"^gasto\s+", "", text.strip(), flags=re.IGNORECASE).strip()
    match = re.match(r"^(\d[\d.,]*)\s+(.+)$", text)
    if not match:
        return None
    amount_str = match.group(1).replace(".", "").replace(",", "")
    if not amount_str.isdigit():
        return None
    merchant = match.group(2).strip()
    if not merchant:
        return None
    return (int(amount_str), merchant)


async def handle_button_click(
    phone: str, button_id: str, context_msg_id: str, db: AsyncSession, redis: Redis
) -> None:
    """Route a WhatsApp button reply to the correct split action."""
    print(f"[WA_BUTTON] from={phone} button_id={button_id} context_msg_id={context_msg_id!r}", flush=True)
    transaction_id = await get_transaction_id_by_msgid(context_msg_id, redis)
    print(f"[WA_BUTTON] transaction_id from msgid lookup={transaction_id!r}", flush=True)
    if not transaction_id:
        return  # message too old or unknown

    session = await get_session(phone, transaction_id, redis)
    print(f"[WA_BUTTON] session={session}", flush=True)
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

        txn_result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
        txn = txn_result.scalar_one_or_none()
        amount_str = f"${txn.amount:,}" if txn else session.raw_merchant

        ranked = await get_user_ranked_categories(txn.user_id, session.raw_merchant, db) if txn else []
        display_cats, overflow = _paginate_categories(ranked)
        session.overflow_categories = overflow
        await save_session(phone, session, redis)

        context_msg = f"¿A qué categoría pertenece el gasto de {amount_str} en {session.raw_merchant}?"
        category_wamid = await send_category_list(to=phone, categories=display_cats, context_msg=context_msg)
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

    # "Otras categorías" is not a real category — show the overflow page instead
    if list_item_title == _OTRAS:
        overflow_wamid = await send_category_list(
            to=phone,
            categories=session.overflow_categories,
            context_msg=f"Otras categorías para {session.raw_merchant}:",
        )
        await save_msgid(overflow_wamid, transaction_id, redis)
        return

    category = list_item_title
    txn = await _save_split(session.transaction_id, session.split_type or "shared", category, db)
    if txn is not None:
        await record_category_selection(
            session.raw_merchant, category, db=db, redis=redis, user_id=txn.user_id
        )
    await clear_session(phone, transaction_id, redis)
    split_label = {"personal": "Personal", "shared": "Compartido"}.get(session.split_type or "shared", session.split_type)
    await send_text(to=phone, body=f"✅ Guardado: {session.raw_merchant} → {category} ({split_label})")


async def _save_split(
    transaction_id: str, split_type: str, category: str | None, db: AsyncSession
) -> Transaction | None:
    result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    txn = result.scalar_one_or_none()
    if not txn:
        return None
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
    return txn


async def _get_user_and_household_by_phone(
    phone: str, db: AsyncSession
) -> tuple[uuid.UUID, uuid.UUID, str] | None:
    """Return (user_id, household_id, preferred_currency) for a verified WhatsApp phone, or None."""
    from modules.auth.models import User
    from modules.households.models import HouseholdMember

    normalized = _normalize_phone(phone)
    result = await db.execute(
        select(User.id, HouseholdMember.household_id, User.preferred_currency)
        .join(HouseholdMember, HouseholdMember.user_id == User.id)
        .where(or_(User.phone_whatsapp == f"+{normalized}", User.phone_whatsapp == normalized))
        .limit(1)
    )
    row = result.first()
    if not row:
        return None
    return (row[0], row[1], row[2])


async def _handle_manual_expense_trigger(
    phone: str, text: str, db: AsyncSession, redis: Redis
) -> None:
    """Create a manual transaction from a parsed expense message and start the session."""
    print(f"[MANUAL_EXPENSE] received from={phone} text={text!r}", flush=True)

    parsed = parse_manual_expense(text)
    if not parsed:
        print(f"[MANUAL_EXPENSE] parse failed, ignoring", flush=True)
        return

    amount, merchant = parsed
    print(f"[MANUAL_EXPENSE] parsed amount={amount} merchant={merchant!r}", flush=True)

    user_row = await _get_user_and_household_by_phone(phone, db)
    if not user_row:
        print(f"[MANUAL_EXPENSE] user not found for phone={phone}", flush=True)
        return

    user_id, household_id, currency = user_row
    print(f"[MANUAL_EXPENSE] user_id={user_id} household_id={household_id} currency={currency}", flush=True)

    txn = Transaction(
        id=uuid.uuid4(),
        user_id=user_id,
        household_id=household_id,
        raw_merchant_name=merchant,
        amount=amount,
        currency=currency,
        transaction_date=datetime.now(timezone.utc),
        source="manual",
        status="confirmed",
        transaction_type="expense",
    )
    db.add(txn)
    await db.flush()
    await db.commit()

    ranked = await get_user_ranked_categories(user_id, merchant, db)
    display_cats, overflow = _paginate_categories(ranked)

    session = WhatsAppSession(
        transaction_id=str(txn.id),
        step="awaiting_split",
        raw_merchant=merchant,
        overflow_categories=overflow,
    )
    await save_session(phone, session, redis)

    wamid = await send_expense_alert(
        to=phone,
        amount=amount,
        merchant=merchant,
        partner_name="tu pareja",
        is_joint=False,
        categories=display_cats,
        currency=currency,
    )
    await save_msgid(wamid, str(txn.id), redis)


async def handle_text_message(
    phone: str, text: str, db: AsyncSession, redis: Redis
) -> None:
    """Handle a free-text reply during an active edit step, or a new manual expense trigger."""
    print(f"[WA_TEXT] from={phone} text={text!r}", flush=True)
    transaction_id = await get_active_edit_transaction_id(phone, redis)
    if not transaction_id:
        await _handle_manual_expense_trigger(phone, text, db, redis)
        return

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

    # Re-send the expense alert with updated data, using user's ranked categories
    ranked = await get_user_ranked_categories(txn.user_id, txn.raw_merchant_name, db)
    display_cats, overflow = _paginate_categories(ranked)
    session.overflow_categories = overflow
    session.step = "awaiting_category" if is_joint else "awaiting_split"

    new_msg_id = await send_expense_alert(
        to=phone,
        amount=txn.amount,
        merchant=txn.raw_merchant_name,
        partner_name="tu pareja",
        is_joint=is_joint,
        categories=display_cats,
        currency=txn.currency or "CLP",
    )
    await save_session(phone, session, redis)
    await save_msgid(new_msg_id, transaction_id, redis)
