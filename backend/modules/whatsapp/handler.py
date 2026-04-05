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
from modules.whatsapp.sender import (
    send_category_list,
    send_text,
    send_edit_options,
    send_expense_alert,
)
from modules.merchants.service import record_category_selection, get_user_ranked_categories
from modules.transactions.models import Transaction, TransactionSplit


def _parse_amount(raw: str, currency: str = "CLP") -> int | None:
    """Parse a human-entered amount string into the DB storage unit.

    USD → stored as cents.  CLP → stored as integer (no decimals).

    Disambiguation rule for '.' and ',':
    - 3 digits after separator → thousands (1.500 = 1500, 25.600 = 25600)
    - 1-2 digits after separator → decimal (USD only; CLP never has decimals)

    Examples (USD):
      "25"      → 2500 cents ($25.00)
      "25.5"    → 2550 cents ($25.50)
      "25.50"   → 2550 cents ($25.50)
      "1,000"   → 100000 cents ($1,000.00)
      "1.500"   → 150000 cents ($1,500.00 — 3 digits = thousands)

    Examples (CLP):
      "25600"   → 25600
      "25.600"  → 25600 (dot = thousands)
      "25,600"  → 25600 (comma = thousands)
      "1.500.000" → 1500000
    """
    raw = raw.strip().lstrip("$")

    if currency == "CLP":
        # CLP: dots and commas are always thousands separators, no decimals
        cleaned = raw.replace(".", "").replace(",", "")
        try:
            return int(cleaned)
        except ValueError:
            return None

    # USD: need to distinguish thousands vs decimal separators
    # Check for the last '.' or ',' — that's the potential decimal separator
    # Replace all commas with dots for uniform handling, then analyze
    last_dot = raw.rfind(".")
    last_comma = raw.rfind(",")
    last_sep = max(last_dot, last_comma)

    if last_sep == -1:
        # No separator: "25" → $25.00 → 2500 cents
        try:
            return int(raw) * 100
        except ValueError:
            return None

    after_sep = raw[last_sep + 1 :]
    if len(after_sep) == 3:
        # 3 digits after separator → thousands: "1.500" or "1,500" → 1500 → 150000 cents
        cleaned = raw.replace(".", "").replace(",", "")
        try:
            return int(cleaned) * 100
        except ValueError:
            return None
    else:
        # 1-2 digits after separator → decimal: "25.5" → $25.50, "25.50" → $25.50
        # Remove thousands separators (everything except the last separator)
        sep_char = raw[last_sep]
        other_char = "," if sep_char == "." else "."
        cleaned = raw.replace(other_char, "")
        # Replace the decimal separator with '.'
        cleaned = cleaned[: cleaned.rfind(sep_char)] + "." + cleaned[cleaned.rfind(sep_char) + 1 :]
        try:
            return int(round(float(cleaned) * 100))
        except ValueError:
            return None


_USD_KEYWORDS = {"usd", "dolares", "dólares", "dollars", "dollar", "dolar", "dólar"}
_CLP_KEYWORDS = {"clp", "pesos", "chile", "chileno", "chilenos"}

# Prefixes stripped before amount+merchant extraction (order matters: longer first)
_PREFIXES = re.compile(
    r"^(?:"
    r"gast[oée]\s+de|gast[oée]|"  # gasto, gasté, gasto de
    r"compra\s+de|compra\s+en|compra|"  # compra, compra de, compra en
    r"transferencia\s+de|transferencia\s+a|transferencia|"  # transferencia, transferencia de/a
    r"pago\s+de|pago\s+en|pago|"  # pago, pago de, pago en
    r"pagué\s+de|pagué|"  # pagué
    r"expense\s+of|expense|"  # expense, expense of
    r"spent|paid|payment\s+of|payment|"  # spent, paid, payment, payment of
    r"transfer\s+to|transfer"  # transfer, transfer to
    r")\s+",
    re.IGNORECASE,
)

# Amount then merchant, with optional "en"/"in"/"at"/"a"/"de" separator
_AMOUNT_MERCHANT = re.compile(
    r"^(\$?\d[\d.,]*)\s+(?:en\s+|in\s+|at\s+|a\s+|de\s+)?(.+)$",
    re.IGNORECASE,
)


def _detect_currency(text: str, default: str) -> tuple[str, str]:
    """Detect currency override from keywords in the message.

    Returns (currency, cleaned_text) with the currency keyword removed.
    """
    words = text.strip().split()
    for i, word in enumerate(words):
        lower = word.lower().rstrip(".,;!?")
        if lower in _USD_KEYWORDS:
            cleaned = " ".join(words[:i] + words[i + 1 :])
            return "USD", cleaned
        if lower in _CLP_KEYWORDS:
            cleaned = " ".join(words[:i] + words[i + 1 :])
            return "CLP", cleaned
    return default, text


def parse_manual_expense(text: str, currency: str = "CLP") -> tuple[int, str] | None:
    """Parse natural-language expense messages into (amount_int, merchant).

    Accepted forms (Spanish & English):
      "gasto 5000 Starbucks"
      "gasto de 5000 en Starbucks"
      "gasté 25.50 en Starbucks"
      "expense of 25 in Starbucks"
      "spent 25 at Starbucks"
      "5000 Starbucks"
      "gasto de 15,000 en Lider clp"  ← currency override

    Amount is returned in DB storage units (CLP integer or USD cents).
    Returns None if the text cannot be interpreted as a manual expense.
    """
    text = text.strip()

    # Detect currency override before stripping keywords
    currency, text = _detect_currency(text, currency)

    # Strip known prefixes
    text = _PREFIXES.sub("", text).strip()

    match = _AMOUNT_MERCHANT.match(text)
    if not match:
        return None
    amount = _parse_amount(match.group(1), currency)
    if amount is None:
        return None
    merchant = match.group(2).strip()
    if not merchant:
        return None
    return (amount, merchant)


async def handle_button_click(
    phone: str, button_id: str, context_msg_id: str, db: AsyncSession, redis: Redis
) -> None:
    """Route a WhatsApp button reply to the correct split action."""
    print(
        f"[WA_BUTTON] from={phone} button_id={button_id} context_msg_id={context_msg_id!r}",
        flush=True,
    )
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
            await send_text(to=phone, body="Escribe el nuevo monto (ej: 25.50 o 15990):")
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
        from modules.whatsapp.sender import _format_amount

        amount_str = (
            _format_amount(txn.amount, txn.currency or "CLP") if txn else session.raw_merchant
        )

        ranked = (
            await get_user_ranked_categories(
                txn.user_id, session.raw_merchant, db, category_type="expense"
            )
            if txn
            else []
        )
        await save_session(phone, session, redis)

        context_msg = (
            f"¿A qué categoría pertenece el gasto de {amount_str} en {session.raw_merchant}?"
        )
        category_wamid = await send_category_list(
            to=phone, categories=ranked[:10], context_msg=context_msg
        )
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
    txn = await _save_split(session.transaction_id, session.split_type or "shared", category, db)
    if txn is not None:
        await record_category_selection(
            session.raw_merchant, category, db=db, redis=redis, user_id=txn.user_id
        )
    await clear_session(phone, transaction_id, redis)
    split_label = {"personal": "Personal", "shared": "Compartido"}.get(
        session.split_type or "shared", session.split_type
    )
    await send_text(
        to=phone, body=f"✅ Guardado: {session.raw_merchant} → {category} ({split_label})"
    )


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

    user_row = await _get_user_and_household_by_phone(phone, db)
    if not user_row:
        print(f"[MANUAL_EXPENSE] user not found for phone={phone}", flush=True)
        return

    user_id, household_id, currency = user_row

    parsed = parse_manual_expense(text, currency)
    if not parsed:
        print("[MANUAL_EXPENSE] parse failed, ignoring", flush=True)
        return

    amount, merchant = parsed
    print(
        f"[MANUAL_EXPENSE] user_id={user_id} household_id={household_id} currency={currency}",
        flush=True,
    )

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

    categories = (await get_user_ranked_categories(user_id, merchant, db, category_type="expense"))[
        :10
    ]

    session = WhatsAppSession(
        transaction_id=str(txn.id),
        step="awaiting_split",
        raw_merchant=merchant,
    )
    await save_session(phone, session, redis)

    wamid = await send_expense_alert(
        to=phone,
        amount=amount,
        merchant=merchant,
        partner_name="tu pareja",
        is_joint=False,
        categories=categories,
        currency=currency,
    )
    await save_msgid(wamid, str(txn.id), redis)


async def handle_text_message(phone: str, text: str, db: AsyncSession, redis: Redis) -> None:
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
        currency = txn.currency or "CLP"
        new_amount = _parse_amount(text.strip(), currency)
        if new_amount is None:
            example = "15990" if currency == "CLP" else "25.50"
            await send_text(to=phone, body=f"❌ Por favor escribe solo el número (ej: {example}).")
            return
        txn.amount = new_amount
    else:
        return  # unexpected step

    await db.commit()
    await clear_active_edit(phone, redis)

    # Determine is_joint from bank account type
    is_joint = False
    if txn.bank_account_id:
        from modules.households.models import BankAccount

        acct_result = await db.execute(
            select(BankAccount).where(BankAccount.id == txn.bank_account_id)
        )
        acct = acct_result.scalar_one_or_none()
        is_joint = acct.account_type == "joint" if acct else False

    # Re-send the expense alert with updated data, using user's ranked expense categories
    categories = (
        await get_user_ranked_categories(
            txn.user_id, txn.raw_merchant_name, db, category_type="expense"
        )
    )[:10]
    session.step = "awaiting_category" if is_joint else "awaiting_split"

    new_msg_id = await send_expense_alert(
        to=phone,
        amount=txn.amount,
        merchant=txn.raw_merchant_name,
        partner_name="tu pareja",
        is_joint=is_joint,
        categories=categories,
        currency=txn.currency or "CLP",
    )
    await save_session(phone, session, redis)
    await save_msgid(new_msg_id, transaction_id, redis)
