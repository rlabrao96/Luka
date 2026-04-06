"""DB-backed bank registry with Redis cache — replaces hardcoded BANK_SENDER_DOMAINS."""

import json
import logging
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.email.models import BankRegistry

logger = logging.getLogger(__name__)

_CACHE_TTL = 86400  # 24h
_CACHE_PREFIX = "bank_reg:"

# Financial keywords — Spanish + English + Portuguese
FINANCIAL_KEYWORDS: list[str] = [
    # Spanish
    "transferencia",
    "compra",
    "pago",
    "transaccion",
    "transacción",
    "tarjeta",
    "debito",
    "débito",
    "credito",
    "crédito",
    "retiro",
    "deposito",
    "depósito",
    "abono",
    "cargo",
    "monto",
    "saldo",
    "cuenta",
    "banco",
    "giro",
    "comision",
    "comisión",
    "cuota",
    "factura",
    "boleta",
    "TEF",
    "PAC",
    "PAT",
    # English
    "transaction",
    "purchase",
    "payment",
    "transfer",
    "debit",
    "credit",
    "withdrawal",
    "deposit",
    "charge",
    "amount",
    "balance",
    "alert",
    "statement",
    "zelle",
    # Portuguese (Brazil)
    "transação",
    "transacao",
    "compra aprovada",
    "cartão",
    "cartao",
    "fatura",
    "pagamento",
    "pix",
    "transferência",
    # Additional Spanish (CO/MX/PE)
    "movimiento",
    "consumo",
    "aviso",
    "alerta",
    "notificación",
    "notificacion",
]


def _extract_domain(sender: str) -> str | None:
    match = re.search(r"@([\w.-]+)", sender)
    return match.group(1).lower() if match else None


async def _lookup_domain(domain: str, *, redis=None, db: AsyncSession | None = None) -> dict | None:
    # L1: Redis cache
    if redis:
        cached = await redis.get(f"{_CACHE_PREFIX}{domain}")
        if cached:
            data = json.loads(cached)
            return data if data != "__miss__" else None

    # L2: DB lookup — exact match, then subdomain match
    if db:
        stmt = select(BankRegistry).where(BankRegistry.bank_domain == domain)
        result = await db.execute(stmt)
        entry = result.scalar_one_or_none()

        if not entry:
            parts = domain.split(".")
            if len(parts) > 2:
                parent = ".".join(parts[1:])
                stmt = select(BankRegistry).where(BankRegistry.bank_domain == parent)
                result = await db.execute(stmt)
                entry = result.scalar_one_or_none()

        if entry:
            data = {
                "bank_domain": entry.bank_domain,
                "bank_name": entry.bank_name,
                "country": entry.country,
                "status": entry.status,
                "active_template_id": str(entry.active_template_id)
                if entry.active_template_id
                else None,
                "known_subjects": entry.known_subjects or [],
                "notification_types": entry.notification_types or [],
            }
            if redis:
                await redis.set(f"{_CACHE_PREFIX}{domain}", json.dumps(data), ex=_CACHE_TTL)
            return data

    if redis:
        await redis.set(f"{_CACHE_PREFIX}{domain}", '"__miss__"', ex=_CACHE_TTL)
    return None


async def is_bank_sender(sender: str, *, redis=None, db: AsyncSession | None = None) -> bool:
    domain = _extract_domain(sender)
    if not domain:
        return False
    meta = await _lookup_domain(domain, redis=redis, db=db)
    if not meta:
        return False
    return meta["status"] == "active"


async def get_bank_name(sender: str, *, redis=None, db: AsyncSession | None = None) -> str:
    domain = _extract_domain(sender)
    if not domain:
        return "Unknown"
    meta = await _lookup_domain(domain, redis=redis, db=db)
    return meta["bank_name"] if meta else "Unknown"


async def get_bank_metadata(
    sender: str, *, redis=None, db: AsyncSession | None = None
) -> dict | None:
    domain = _extract_domain(sender)
    if not domain:
        return None
    return await _lookup_domain(domain, redis=redis, db=db)


def is_financial_email(subject: str, sender: str, body: str) -> bool:
    combined = f"{subject} {sender} {body}".lower()
    return any(kw in combined for kw in FINANCIAL_KEYWORDS)
