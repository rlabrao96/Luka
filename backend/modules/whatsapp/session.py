import json
from dataclasses import dataclass, asdict
from redis.asyncio import Redis

_SESSION_TTL = 1800  # 30 minutes


@dataclass
class WhatsAppSession:
    transaction_id: str
    step: str  # 'awaiting_split' | 'awaiting_category'
    split_type: str = ""
    raw_merchant: str = ""


def _normalize_phone(phone: str) -> str:
    """Strip leading + so session keys are consistent regardless of format."""
    return phone.lstrip("+")


async def save_session(phone: str, session: WhatsAppSession, redis: Redis) -> None:
    await redis.setex(
        f"wa_session:{_normalize_phone(phone)}", _SESSION_TTL, json.dumps(asdict(session))
    )


async def get_session(phone: str, redis: Redis) -> WhatsAppSession | None:
    raw = await redis.get(f"wa_session:{_normalize_phone(phone)}")
    if not raw:
        return None
    data = json.loads(raw)
    return WhatsAppSession(**data)


async def clear_session(phone: str, redis: Redis) -> None:
    await redis.delete(f"wa_session:{_normalize_phone(phone)}")
