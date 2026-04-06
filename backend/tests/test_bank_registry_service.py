"""Tests for bank_registry_service — async DB-backed bank lookups with Redis cache."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from modules.email.bank_registry_service import (
    is_bank_sender,
    get_bank_name,
    get_bank_metadata,
    is_financial_email,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


ACTIVE_BANK_DATA = {
    "bank_domain": "bancochile.cl",
    "bank_name": "Banco de Chile",
    "country": "CL",
    "status": "active",
    "active_template_id": None,
    "known_subjects": ["Transferencia a Terceros"],
    "notification_types": ["transfer", "purchase"],
}

PUSH_ONLY_BANK_DATA = {
    "bank_domain": "legacy.cl",
    "bank_name": "Banco Legacy",
    "country": "CL",
    "status": "push_only",
    "active_template_id": None,
    "known_subjects": [],
    "notification_types": [],
}


def make_redis_hit(data: dict) -> AsyncMock:
    """Redis mock that returns a cached entry."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=json.dumps(data).encode())
    redis.set = AsyncMock()
    return redis


def make_redis_miss() -> AsyncMock:
    """Redis mock that returns None (cache miss)."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    return redis


def make_db_returning(entry) -> AsyncMock:
    """DB session mock that returns a single ORM-like entry."""
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = entry
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_mock)
    return db


def make_db_miss() -> AsyncMock:
    """DB session mock that returns None for all queries."""
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_mock)
    return db


def make_bank_entry(data: dict):
    """Create a fake ORM BankRegistry-like object from a dict."""
    entry = MagicMock()
    entry.bank_domain = data["bank_domain"]
    entry.bank_name = data["bank_name"]
    entry.country = data["country"]
    entry.status = data["status"]
    entry.active_template_id = data["active_template_id"]
    entry.known_subjects = data["known_subjects"]
    entry.notification_types = data["notification_types"]
    return entry


# ── Test 1: is_bank_sender — known active domain via Redis cache ─────────────


@pytest.mark.asyncio
async def test_is_bank_sender_redis_cache_hit_active():
    """Returns True for a known active domain when Redis returns cached data."""
    redis = make_redis_hit(ACTIVE_BANK_DATA)
    result = await is_bank_sender("noti@bancochile.cl", redis=redis)
    assert result is True
    redis.get.assert_called_once_with("bank_reg:bancochile.cl")


# ── Test 2: is_bank_sender — unknown domain (Redis miss + DB miss) ───────────


@pytest.mark.asyncio
async def test_is_bank_sender_unknown_domain_false():
    """Returns False when domain not found in Redis or DB."""
    redis = make_redis_miss()
    db = make_db_miss()
    result = await is_bank_sender("promo@tienda.cl", redis=redis, db=db)
    assert result is False
    # Should write __miss__ sentinel to Redis
    redis.set.assert_called_once()
    call_args = redis.set.call_args
    assert '"__miss__"' in call_args[0][1]


# ── Test 3: is_bank_sender — push_only bank returns False ───────────────────


@pytest.mark.asyncio
async def test_is_bank_sender_push_only_returns_false():
    """Returns False for push_only banks (not fully integrated)."""
    redis = make_redis_hit(PUSH_ONLY_BANK_DATA)
    result = await is_bank_sender("noti@legacy.cl", redis=redis)
    assert result is False


# ── Test 4: get_bank_metadata — returns full entry dict ─────────────────────


@pytest.mark.asyncio
async def test_get_bank_metadata_returns_full_dict():
    """Returns complete metadata dict for a known bank."""
    redis = make_redis_hit(ACTIVE_BANK_DATA)
    meta = await get_bank_metadata("envio@bancochile.cl", redis=redis)
    assert meta is not None
    assert meta["bank_domain"] == "bancochile.cl"
    assert meta["bank_name"] == "Banco de Chile"
    assert meta["country"] == "CL"
    assert meta["status"] == "active"
    assert meta["known_subjects"] == ["Transferencia a Terceros"]
    assert meta["notification_types"] == ["transfer", "purchase"]


# ── Test 5: get_bank_name — returns display name ────────────────────────────


@pytest.mark.asyncio
async def test_get_bank_name_returns_display_name():
    """Returns bank_name string for known sender."""
    redis = make_redis_hit(ACTIVE_BANK_DATA)
    name = await get_bank_name("noti@bancochile.cl", redis=redis)
    assert name == "Banco de Chile"


@pytest.mark.asyncio
async def test_get_bank_name_unknown_returns_unknown():
    """Returns 'Unknown' when domain is not found."""
    redis = make_redis_miss()
    db = make_db_miss()
    name = await get_bank_name("promo@tienda.cl", redis=redis, db=db)
    assert name == "Unknown"


# ── Test 6: is_financial_email — matches Spanish keywords ───────────────────


def test_is_financial_email_spanish_keywords():
    """Detects financial emails with Spanish keywords."""
    assert is_financial_email(
        subject="Transferencia realizada",
        sender="noti@banco.cl",
        body="Se ha realizado una transferencia de $50.000",
    )
    assert is_financial_email(
        subject="Aviso de compra",
        sender="noti@banco.cl",
        body="Se realizó una compra con tu tarjeta de débito",
    )
    assert is_financial_email(
        subject="Abono recibido",
        sender="noti@banco.cl",
        body="Se acreditó un abono en su cuenta",
    )


# ── Test 7: is_financial_email — matches Portuguese keywords ────────────────


def test_is_financial_email_portuguese_keywords():
    """Detects financial emails with Portuguese/Brazilian keywords."""
    assert is_financial_email(
        subject="Compra aprovada",
        sender="noti@bradesco.com.br",
        body="Sua compra aprovada no cartão foi processada",
    )
    assert is_financial_email(
        subject="Pix recebido",
        sender="noti@nubank.com.br",
        body="Você recebeu um pix de R$200,00",
    )
    assert is_financial_email(
        subject="Fatura disponível",
        sender="noti@itau.com.br",
        body="Sua fatura do cartão está disponível",
    )


# ── Test 8: is_financial_email — matches English keywords ───────────────────


def test_is_financial_email_english_keywords():
    """Detects financial emails with English keywords."""
    assert is_financial_email(
        subject="Transaction Alert",
        sender="alerts@chase.com",
        body="A transaction was made on your account",
    )
    assert is_financial_email(
        subject="Zelle payment received",
        sender="alerts@pnc.com",
        body="You received a Zelle payment of $150.00",
    )
    assert is_financial_email(
        subject="Low balance alert",
        sender="alerts@bankofamerica.com",
        body="Your available balance is below $100",
    )


# ── Test 9: is_financial_email — returns False for non-financial text ────────


def test_is_financial_email_rejects_non_financial():
    """Returns False for clearly non-financial emails."""
    assert not is_financial_email(
        subject="Welcome to our newsletter",
        sender="marketing@store.com",
        body="Check out our latest deals and promotions this week!",
    )
    assert not is_financial_email(
        subject="Hola, cómo estás?",
        sender="amigo@gmail.com",
        body="Te escribo para coordinar la junta del viernes",
    )


# ── Test 10: get_bank_metadata — DB fallback when Redis misses ───────────────


@pytest.mark.asyncio
async def test_get_bank_metadata_db_fallback():
    """Falls back to DB when Redis misses, then caches the result."""
    redis = make_redis_miss()
    orm_entry = make_bank_entry(ACTIVE_BANK_DATA)
    db = make_db_returning(orm_entry)

    meta = await get_bank_metadata("noti@bancochile.cl", redis=redis, db=db)

    assert meta is not None
    assert meta["bank_name"] == "Banco de Chile"
    assert meta["status"] == "active"
    # Result should be cached back to Redis
    redis.set.assert_called_once()
    set_args = redis.set.call_args[0]
    assert set_args[0] == "bank_reg:bancochile.cl"
    cached = json.loads(set_args[1])
    assert cached["bank_name"] == "Banco de Chile"


# ── Test 11: subdomain matching via DB ──────────────────────────────────────


@pytest.mark.asyncio
async def test_is_bank_sender_subdomain_db_lookup():
    """Falls through to parent domain lookup for subdomains (e.g. noti.bancochile.cl)."""
    redis = make_redis_miss()

    # First DB query (exact: noti.bancochile.cl) misses, second (bancochile.cl) hits
    miss_result = MagicMock()
    miss_result.scalar_one_or_none.return_value = None
    hit_result = MagicMock()
    hit_result.scalar_one_or_none.return_value = make_bank_entry(ACTIVE_BANK_DATA)

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[miss_result, hit_result])

    result = await is_bank_sender("alert@noti.bancochile.cl", redis=redis, db=db)
    assert result is True


# ── Test 12: no domain in sender ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_is_bank_sender_no_domain():
    """Returns False when sender string has no email address."""
    result = await is_bank_sender("not-an-email")
    assert result is False


@pytest.mark.asyncio
async def test_get_bank_metadata_no_domain():
    """Returns None when sender string has no email address."""
    result = await get_bank_metadata("not-an-email")
    assert result is None


@pytest.mark.asyncio
async def test_get_bank_name_no_domain():
    """Returns 'Unknown' when sender string has no email address."""
    result = await get_bank_name("not-an-email")
    assert result == "Unknown"
