import json
from dataclasses import dataclass, asdict
from redis.asyncio import Redis

_SESSION_TTL = 86400  # 24 hours


@dataclass
class WhatsAppSession:
    transaction_id: str
    step: str  # 'awaiting_split' | 'awaiting_category'
    split_type: str = ""
    raw_merchant: str = ""


def _normalize_phone(phone: str) -> str:
    """Strip leading + so session keys are consistent regardless of format."""
    return phone.lstrip("+")


def _session_key(phone: str, txn_id: str) -> str:
    return f"wa_session:{_normalize_phone(phone)}:{txn_id}"


async def save_session(phone: str, session: WhatsAppSession, redis: Redis) -> None:
    await redis.setex(
        _session_key(phone, session.transaction_id), _SESSION_TTL, json.dumps(asdict(session))
    )


async def get_session(phone: str, txn_id: str, redis: Redis) -> WhatsAppSession | None:
    raw = await redis.get(_session_key(phone, txn_id))
    if not raw:
        return None
    data = json.loads(raw)
    return WhatsAppSession(**data)


async def clear_session(phone: str, txn_id: str, redis: Redis) -> None:
    await redis.delete(_session_key(phone, txn_id))


async def save_msgid(wamid: str, transaction_id: str, redis: Redis) -> None:
    """Map a WhatsApp message ID to a transaction ID so replies can find the right session."""
    await redis.setex(f"wa_msgid:{wamid}", _SESSION_TTL, transaction_id)


async def get_transaction_id_by_msgid(wamid: str, redis: Redis) -> str | None:
    """Look up transaction ID from a WhatsApp message ID. Returns None if expired/unknown."""
    value = await redis.get(f"wa_msgid:{wamid}")
    if value is None:
        return None
    # redis.get() returns bytes when decode_responses=True is not set on the client
    return value.decode() if isinstance(value, bytes) else value


def _active_edit_key(phone: str) -> str:
    return f"wa_active_edit:{_normalize_phone(phone)}"


async def save_active_edit(phone: str, transaction_id: str, redis: Redis) -> None:
    """Mark a phone as being in free-text edit mode for a given transaction."""
    await redis.setex(_active_edit_key(phone), _SESSION_TTL, transaction_id)


async def get_active_edit_transaction_id(phone: str, redis: Redis) -> str | None:
    """Return the transaction_id currently awaiting a free-text edit reply, or None."""
    value = await redis.get(_active_edit_key(phone))
    if value is None:
        return None
    return value.decode() if isinstance(value, bytes) else value


async def clear_active_edit(phone: str, redis: Redis) -> None:
    """Remove active-edit marker after the edit is processed."""
    await redis.delete(_active_edit_key(phone))
