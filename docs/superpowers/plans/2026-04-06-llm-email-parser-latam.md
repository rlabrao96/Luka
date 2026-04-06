# LLM Email Parser for LATAM Expansion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace regex-based email parsing with a three-layer system (templates, LLM waterfall, regex fallback) to support any bank in any LATAM country without manual template work.

**Architecture:** Emails hit a declarative template first (free, 5ms), fall through to a Gemini confidence waterfall (4 models, $0.0005/tx), then legacy regex as last resort. An autonomous Template Agent runs daily, generating and validating declarative JSON templates from LLM-parsed data, promoting/retiring them without human intervention.

**Tech Stack:** Gemini 3.1 Flash Lite / 2.5 Flash / 3 Flash / 2.5 Pro (waterfall), BeautifulSoup (template execution), SQLAlchemy async (new tables), ARQ cron (Template Agent), Redis (bank registry cache)

**Spec:** `docs/superpowers/specs/2026-04-06-llm-email-parser-latam-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `backend/modules/email/llm_parser.py` | LLM extraction with confidence waterfall — calls Gemini, returns ParsedEmail |
| `backend/modules/email/template_executor.py` | Interprets declarative JSON templates — CSS selectors + regex + fixed transforms |
| `backend/modules/email/template_agent.py` | Autonomous daily job — discover, generate, validate, promote, monitor, rollback templates |
| `backend/modules/email/bank_registry_service.py` | DB-backed bank registry — replaces hardcoded BANK_SENDER_DOMAINS |
| `backend/modules/email/models.py` | SQLAlchemy models — EmailTemplate, ParsedEmailLog, BankRegistry |
| `backend/alembic/versions/030_llm_parser_tables.py` | Alembic migration — 3 new tables + RLS + seed data |
| `backend/tests/test_llm_parser.py` | Tests for LLM parser waterfall logic |
| `backend/tests/test_template_executor.py` | Tests for declarative template execution |
| `backend/tests/test_template_agent.py` | Tests for Template Agent lifecycle |
| `backend/tests/test_bank_registry_service.py` | Tests for bank registry service |

### Modified Files

| File | Changes |
|------|---------|
| `backend/modules/email/base.py` | Add `transfer_recipient`, `card_last_four`, `confidence` fields to ParsedEmail |
| `backend/modules/email/parser.py` | Rename `parse_bank_email()` → `parse_bank_email_regex()`, new `parse_bank_email()` orchestrator |
| `backend/modules/email/filter.py` | Replace `BANK_SENDER_DOMAINS` with bank_registry_service lookups, add Portuguese keywords |
| `backend/jobs/tasks.py` | Add `parsed_email_log` writing after parsing, add `purge_email_logs` job |
| `backend/worker.py` | Add `template_agent` cron to SlowWorkerSettings, add `purge_email_logs` cron to FastWorkerSettings |
| `backend/core/config.py` | Add waterfall thresholds, shadow validation rate, template agent settings |

---

## Task 1: Database Migration — New Tables + Seed Data

**Files:**
- Create: `backend/modules/email/models.py`
- Create: `backend/alembic/versions/030_llm_parser_tables.py`

- [ ] **Step 1: Create SQLAlchemy models**

Create `backend/modules/email/models.py`:

```python
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey,
    UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from core.database import Base


class BankRegistry(Base):
    __tablename__ = "bank_registry"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bank_domain = Column(String, unique=True, nullable=False, index=True)
    bank_name = Column(String, nullable=False)
    country = Column(String(2), nullable=False, index=True)
    known_subjects = Column(JSONB, default=list)
    notification_types = Column(JSONB, default=list)
    active_template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("email_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    email_count = Column(Integer, default=0)
    status = Column(String, default="active")  # active | push_only | deprecated
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bank_domain = Column(String, nullable=False, index=True)
    country = Column(String(2), nullable=False)
    template_code = Column(JSONB, nullable=False)  # declarative extraction template
    template_hash = Column(String(64), nullable=False)
    status = Column(String, default="candidate")  # candidate | active | retired | failed
    validated_count = Column(Integer, default=0)
    accuracy = Column(Float, default=0.0)
    promoted_at = Column(DateTime(timezone=True), nullable=True)
    retired_at = Column(DateTime(timezone=True), nullable=True)
    retired_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ParsedEmailLog(Base):
    __tablename__ = "parsed_email_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    bank_domain = Column(String, nullable=False, index=True)
    country = Column(String(2), nullable=True)
    raw_email_html = Column(Text, nullable=True)  # purged after 7 days
    llm_extraction = Column(JSONB, nullable=True)
    template_extraction = Column(JSONB, nullable=True)
    parser_used = Column(String, nullable=False)  # llm | template | regex
    llm_model_used = Column(String, nullable=True)
    shadow_match = Column(Boolean, nullable=True)
    waterfall_depth = Column(Integer, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
```

- [ ] **Step 2: Create Alembic migration**

Create `backend/alembic/versions/030_llm_parser_tables.py`:

```python
"""Add LLM parser tables: email_templates, parsed_email_log, bank_registry"""

revision = "030"
down_revision = "029"

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


def upgrade() -> None:
    # email_templates (must be created first — bank_registry references it)
    op.create_table(
        "email_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("bank_domain", sa.String(), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("template_code", JSONB, nullable=False),
        sa.Column("template_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(), server_default="candidate"),
        sa.Column("validated_count", sa.Integer(), server_default="0"),
        sa.Column("accuracy", sa.Float(), server_default="0.0"),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_email_templates_bank_domain", "email_templates", ["bank_domain"])

    # bank_registry
    op.create_table(
        "bank_registry",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("bank_domain", sa.String(), nullable=False, unique=True),
        sa.Column("bank_name", sa.String(), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("known_subjects", JSONB, server_default="'[]'::jsonb"),
        sa.Column("notification_types", JSONB, server_default="'[]'::jsonb"),
        sa.Column("active_template_id", UUID(as_uuid=True),
                  sa.ForeignKey("email_templates.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("email_count", sa.Integer(), server_default="0"),
        sa.Column("status", sa.String(), server_default="active"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_bank_registry_bank_domain", "bank_registry", ["bank_domain"],
                    unique=True)
    op.create_index("ix_bank_registry_country", "bank_registry", ["country"])

    # parsed_email_log
    op.create_table(
        "parsed_email_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bank_domain", sa.String(), nullable=False),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("raw_email_html", sa.Text(), nullable=True),
        sa.Column("llm_extraction", JSONB, nullable=True),
        sa.Column("template_extraction", JSONB, nullable=True),
        sa.Column("parser_used", sa.String(), nullable=False),
        sa.Column("llm_model_used", sa.String(), nullable=True),
        sa.Column("shadow_match", sa.Boolean(), nullable=True),
        sa.Column("waterfall_depth", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_parsed_email_log_bank_domain", "parsed_email_log",
                    ["bank_domain"])
    op.create_index("ix_parsed_email_log_created_at", "parsed_email_log",
                    ["created_at"])

    # RLS for parsed_email_log
    op.execute("ALTER TABLE parsed_email_log ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY parsed_email_log_user_isolation ON parsed_email_log
        USING (user_id = auth.uid())
    """)

    # Seed bank_registry with baseline banks
    _seed_bank_registry()


def _seed_bank_registry() -> None:
    """Seed with 30+ LATAM banks from spec + existing BANK_SENDER_DOMAINS."""
    from sqlalchemy import text
    conn = op.get_bind()

    banks = [
        # Chile
        ("bancochile.cl", "Banco de Chile", "CL", "active"),
        ("bancoestado.cl", "BancoEstado", "CL", "active"),
        ("santander.cl", "Santander Chile", "CL", "active"),
        ("bci.cl", "BCI", "CL", "active"),
        ("bcidigital.cl", "BCI Digital", "CL", "active"),
        ("bancofalabella.cl", "Banco Falabella", "CL", "active"),
        ("scotiabank.cl", "Scotiabank Chile", "CL", "active"),
        ("bfranceschile.cl", "BBVA Chile", "CL", "active"),
        ("bicecorp.cl", "BICE", "CL", "active"),
        ("itau.cl", "Itau Chile", "CL", "active"),
        ("bancoripley.cl", "Banco Ripley", "CL", "active"),
        ("consorcio.cl", "Banco Consorcio", "CL", "active"),
        ("bancosecurity.cl", "Banco Security", "CL", "active"),
        ("bancointernacional.cl", "Banco Internacional", "CL", "active"),
        ("coopeuch.cl", "Coopeuch", "CL", "active"),
        ("mercadopago.cl", "Mercado Pago Chile", "CL", "active"),
        ("tenpo.cl", "Tenpo", "CL", "active"),
        ("bbva.cl", "BBVA Chile", "CL", "active"),
        ("bbva.com", "BBVA", "CL", "active"),
        ("hsbc.cl", "HSBC Chile", "CL", "active"),
        ("hsbc.com", "HSBC", "CL", "active"),
        ("mercadopago.com", "Mercado Pago", "CL", "active"),
        ("mercadolibre.cl", "Mercado Libre Chile", "CL", "active"),
        ("mercadolibre.com", "Mercado Libre", "CL", "active"),
        ("somosmach.com", "Mach", "CL", "active"),
        ("tapp.cl", "TAPP", "CL", "active"),
        ("losheroes.cl", "Los Heroes", "CL", "active"),
        ("copec.cl", "Copec", "CL", "active"),
        ("copecpay.cl", "Copec Pay", "CL", "active"),
        ("dale.cl", "Dale", "CL", "active"),
        # Colombia
        ("notificacionesbancolombia.com", "Bancolombia", "CO", "active"),
        ("bancolombia.com.co", "Bancolombia", "CO", "active"),
        ("davivienda.com", "Davivienda", "CO", "active"),
        ("bancodebogota.com.co", "Banco de Bogota", "CO", "active"),
        ("bbva.com.co", "BBVA Colombia", "CO", "active"),
        ("nequi.com.co", "Nequi", "CO", "push_only"),
        # Mexico
        ("bbva.mx", "BBVA Mexico", "MX", "active"),
        ("email.bbva.mx", "BBVA Mexico", "MX", "active"),
        ("banorte.com", "Banorte", "MX", "active"),
        ("banamex.com", "Citibanamex", "MX", "active"),
        ("citibanamex.com", "Citibanamex", "MX", "active"),
        ("notificaciones.santander.com.mx", "Santander Mexico", "MX", "active"),
        ("santander.com.mx", "Santander Mexico", "MX", "active"),
        ("nu.com.mx", "Nu Mexico", "MX", "push_only"),
        # Peru
        ("bcp.com.pe", "BCP", "PE", "active"),
        ("viabcp.com", "BCP", "PE", "active"),
        ("interbank.pe", "Interbank", "PE", "active"),
        ("interbank.com.pe", "Interbank", "PE", "active"),
        ("bbva.pe", "BBVA Peru", "PE", "active"),
        ("scotiabank.com.pe", "Scotiabank Peru", "PE", "active"),
        ("yape.com.pe", "Yape", "PE", "push_only"),
        # Brazil
        ("nubank.com.br", "Nubank", "BR", "active"),
        ("novidades.nubank.com.br", "Nubank", "BR", "active"),
        ("itau.com.br", "Itau", "BR", "active"),
        ("itau-unibanco.com.br", "Itau", "BR", "active"),
        ("bradesco.com.br", "Bradesco", "BR", "active"),
        ("bb.com.br", "Banco do Brasil", "BR", "push_only"),
        ("bancointer.com.br", "Banco Inter", "BR", "active"),
        ("inter.co", "Banco Inter", "BR", "active"),
        # USA
        ("ealerts.bankofamerica.com", "Bank of America", "US", "active"),
        ("bankofamerica.com", "Bank of America", "US", "active"),
        ("chase.com", "Chase", "US", "active"),
        ("alertsp.chase.com", "Chase", "US", "active"),
        ("notify.wellsfargo.com", "Wells Fargo", "US", "active"),
        ("wellsfargo.com", "Wells Fargo", "US", "active"),
        ("citi.com", "Citi", "US", "active"),
        ("citibank.com", "Citi", "US", "active"),
        ("info3.citibank.com", "Citi", "US", "active"),
        ("pnc.com", "PNC", "US", "active"),
        # USA — additional banks from existing filter.py
        ("jpmorgan.com", "JPMorgan", "US", "active"),
        ("capitalone.com", "Capital One", "US", "active"),
        ("usbank.com", "US Bank", "US", "active"),
        ("truist.com", "Truist", "US", "active"),
        ("td.com", "TD Bank", "US", "active"),
        ("tdbank.com", "TD Bank", "US", "active"),
        ("regions.com", "Regions", "US", "active"),
        ("53.com", "Fifth Third Bank", "US", "active"),
        ("fifththird.com", "Fifth Third Bank", "US", "active"),
        ("key.com", "KeyBank", "US", "active"),
        ("keybank.com", "KeyBank", "US", "active"),
        ("citizensbank.com", "Citizens Bank", "US", "active"),
        ("ally.com", "Ally", "US", "active"),
        ("discover.com", "Discover", "US", "active"),
        ("americanexpress.com", "American Express", "US", "active"),
        ("aexp.com", "American Express", "US", "active"),
        ("gs.com", "Goldman Sachs", "US", "active"),
        ("marcus.com", "Marcus", "US", "active"),
        ("schwab.com", "Charles Schwab", "US", "active"),
        ("fidelity.com", "Fidelity", "US", "active"),
        ("synchrony.com", "Synchrony", "US", "active"),
        ("navyfederal.org", "Navy Federal", "US", "active"),
        ("usaa.com", "USAA", "US", "active"),
        # USA fintechs
        ("sofi.com", "SoFi", "US", "active"),
        ("chime.com", "Chime", "US", "active"),
        ("venmo.com", "Venmo", "US", "active"),
        ("paypal.com", "PayPal", "US", "active"),
        ("zellepay.com", "Zelle", "US", "active"),
        ("cash.app", "Cash App", "US", "active"),
        ("robinhood.com", "Robinhood", "US", "active"),
        ("wealthfront.com", "Wealthfront", "US", "active"),
        ("betterment.com", "Betterment", "US", "active"),
        ("coinbase.com", "Coinbase", "US", "active"),
    ]

    for domain, name, country, status in banks:
        conn.execute(text("""
            INSERT INTO bank_registry (bank_domain, bank_name, country, status)
            VALUES (:domain, :name, :country, :status)
            ON CONFLICT (bank_domain) DO NOTHING
        """), {"domain": domain, "name": name, "country": country, "status": status})


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS parsed_email_log_user_isolation ON parsed_email_log")
    op.drop_table("parsed_email_log")
    op.drop_table("bank_registry")
    op.drop_table("email_templates")
```

- [ ] **Step 3: Verify migration compiles**

Run: `cd backend && python -c "from alembic.versions import *; print('OK')"`

- [ ] **Step 4: Commit**

```bash
git add backend/modules/email/models.py backend/alembic/versions/030_llm_parser_tables.py
git commit -m "feat: add LLM parser DB models and migration (email_templates, parsed_email_log, bank_registry)"
```

---

## Task 2: Extend ParsedEmail Dataclass + Config

**Files:**
- Modify: `backend/modules/email/base.py:16-23`
- Modify: `backend/core/config.py`

- [ ] **Step 1: Add new fields to ParsedEmail**

In `backend/modules/email/base.py`, update the `ParsedEmail` dataclass:

```python
@dataclass
class ParsedEmail:
    amount: int
    raw_merchant: str
    transaction_date: datetime
    bank_name: str
    transaction_type: str = "expense"
    currency: str = "CLP"
    transfer_recipient: str | None = None
    card_last_four: str | None = None
    confidence: float | None = None
```

The new fields (`transfer_recipient`, `card_last_four`, `confidence`) default to `None` so existing callers (regex parser) are unaffected.

- [ ] **Step 2: Add waterfall config to Settings**

In `backend/core/config.py`, add after the `gemini_api_key` line:

```python
    # LLM parser waterfall thresholds (confidence scores)
    llm_waterfall_thresholds: str = "0.9,0.8,0.7,0.0"  # Flash Lite, 2.5 Flash, 3 Flash, 2.5 Pro
    llm_shadow_validation_rate: float = 0.25  # 25% in month 1, tune down later
    template_agent_min_emails: int = 20  # minimum emails before template generation
    template_agent_recency_days: int = 14  # recent emails required
    template_agent_recency_min: int = 5  # minimum recent emails
```

- [ ] **Step 3: Verify existing tests still pass**

Run: `cd backend && python -m pytest tests/test_email_parser.py -v`
Expected: All existing tests PASS (new fields default to None)

- [ ] **Step 4: Commit**

```bash
git add backend/modules/email/base.py backend/core/config.py
git commit -m "feat: extend ParsedEmail with LLM fields + add waterfall config"
```

---

## Task 3: Bank Registry Service — Replace Hardcoded Domains

**Files:**
- Create: `backend/modules/email/bank_registry_service.py`
- Create: `backend/tests/test_bank_registry_service.py`
- Modify: `backend/modules/email/filter.py`

- [ ] **Step 1: Write failing tests for bank registry service**

Create `backend/tests/test_bank_registry_service.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from modules.email.bank_registry_service import (
    is_bank_sender,
    get_bank_name,
    get_bank_metadata,
    is_financial_email,
)


@pytest.mark.asyncio
async def test_is_bank_sender_known_domain():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = '{"bank_domain":"bancochile.cl","bank_name":"Banco de Chile","country":"CL","status":"active"}'
    result = await is_bank_sender("enviodigital@bancochile.cl", redis=mock_redis)
    assert result is True


@pytest.mark.asyncio
async def test_is_bank_sender_unknown_domain():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    result = await is_bank_sender("spam@random.com", redis=mock_redis, db=mock_db)
    assert result is False


@pytest.mark.asyncio
async def test_is_bank_sender_push_only_skipped():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = '{"bank_domain":"nequi.com.co","bank_name":"Nequi","country":"CO","status":"push_only"}'
    result = await is_bank_sender("alertas@nequi.com.co", redis=mock_redis)
    assert result is False


@pytest.mark.asyncio
async def test_get_bank_metadata_returns_full_entry():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = '{"bank_domain":"bancochile.cl","bank_name":"Banco de Chile","country":"CL","status":"active","active_template_id":null,"known_subjects":["Comprobante de compra"]}'
    meta = await get_bank_metadata("enviodigital@bancochile.cl", redis=mock_redis)
    assert meta is not None
    assert meta["country"] == "CL"
    assert meta["bank_name"] == "Banco de Chile"


@pytest.mark.asyncio
async def test_get_bank_name_returns_display_name():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = '{"bank_domain":"bancochile.cl","bank_name":"Banco de Chile","country":"CL","status":"active"}'
    name = await get_bank_name("enviodigital@bancochile.cl", redis=mock_redis)
    assert name == "Banco de Chile"


def test_is_financial_email_spanish_keywords():
    assert is_financial_email("Comprobante de compra", "banco@test.cl", "") is True
    assert is_financial_email("Newsletter", "marketing@test.cl", "") is False


def test_is_financial_email_portuguese_keywords():
    assert is_financial_email("Compra aprovada no cartao", "nubank@nubank.com.br", "") is True
    assert is_financial_email("", "", "Sua transacao Pix foi realizada") is True


def test_is_financial_email_english_keywords():
    assert is_financial_email("Your credit card transaction", "alerts@chase.com", "") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_bank_registry_service.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Implement bank registry service**

Create `backend/modules/email/bank_registry_service.py`:

```python
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
    "transferencia", "compra", "pago", "transaccion", "transacción",
    "tarjeta", "debito", "débito", "credito", "crédito",
    "retiro", "deposito", "depósito", "abono", "cargo",
    "monto", "saldo", "cuenta", "banco", "giro",
    "comision", "comisión", "cuota", "factura", "boleta",
    "TEF", "PAC", "PAT",
    # English
    "transaction", "purchase", "payment", "transfer", "debit",
    "credit", "withdrawal", "deposit", "charge", "amount",
    "balance", "alert", "statement", "zelle",
    # Portuguese (Brazil)
    "transação", "transacao", "compra aprovada", "cartão", "cartao",
    "fatura", "pagamento", "pix", "transferência",
    # Additional Spanish (CO/MX/PE)
    "movimiento", "consumo", "aviso", "alerta",
    "notificación", "notificacion",
]


def _extract_domain(sender: str) -> str | None:
    """Extract domain from 'Name <email@domain>' or 'email@domain'."""
    match = re.search(r"@([\w.-]+)", sender)
    return match.group(1).lower() if match else None


async def _lookup_domain(
    domain: str, *, redis=None, db: AsyncSession | None = None
) -> dict | None:
    """Look up bank by domain: Redis cache (L1) → DB (L2). Returns dict or None."""
    # L1: Redis cache
    if redis:
        cached = await redis.get(f"{_CACHE_PREFIX}{domain}")
        if cached:
            data = json.loads(cached)
            return data if data != "__miss__" else None

    # L2: DB lookup — try exact match, then subdomain match
    if db:
        # Exact match
        stmt = select(BankRegistry).where(BankRegistry.bank_domain == domain)
        result = await db.execute(stmt)
        entry = result.scalar_one_or_none()

        # Subdomain match: if domain is "ealerts.bankofamerica.com", try "bankofamerica.com"
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
                "active_template_id": str(entry.active_template_id) if entry.active_template_id else None,
                "known_subjects": entry.known_subjects or [],
                "notification_types": entry.notification_types or [],
            }
            if redis:
                await redis.set(f"{_CACHE_PREFIX}{domain}", json.dumps(data), ex=_CACHE_TTL)
            return data

    # Cache miss
    if redis:
        await redis.set(f"{_CACHE_PREFIX}{domain}", '"__miss__"', ex=_CACHE_TTL)
    return None


async def is_bank_sender(sender: str, *, redis=None, db: AsyncSession | None = None) -> bool:
    """Check if sender is from a known, active bank."""
    domain = _extract_domain(sender)
    if not domain:
        return False
    meta = await _lookup_domain(domain, redis=redis, db=db)
    if not meta:
        return False
    return meta["status"] == "active"


async def get_bank_name(sender: str, *, redis=None, db: AsyncSession | None = None) -> str:
    """Return display-friendly bank name for sender."""
    domain = _extract_domain(sender)
    if not domain:
        return "Unknown"
    meta = await _lookup_domain(domain, redis=redis, db=db)
    return meta["bank_name"] if meta else "Unknown"


async def get_bank_metadata(
    sender: str, *, redis=None, db: AsyncSession | None = None
) -> dict | None:
    """Return full bank registry entry for LLM context."""
    domain = _extract_domain(sender)
    if not domain:
        return None
    return await _lookup_domain(domain, redis=redis, db=db)


def is_financial_email(subject: str, sender: str, body: str) -> bool:
    """Check if email contains financial keywords (Spanish + English + Portuguese)."""
    combined = f"{subject} {sender} {body}".lower()
    return any(kw in combined for kw in FINANCIAL_KEYWORDS)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_bank_registry_service.py -v`
Expected: All PASS

- [ ] **Step 5: Update filter.py to use new service**

In `backend/modules/email/filter.py`, keep the file but add a deprecation note at the top and keep `is_financial_email` as a sync fallback. The async versions in `bank_registry_service.py` are the new primary interface. The existing `BANK_SENDER_DOMAINS` dict stays as a fallback for when DB is unavailable.

Add at the top of `filter.py`:

```python
# DEPRECATED: Use bank_registry_service.py for async DB-backed lookups.
# This module is kept as a sync fallback when DB is unavailable.
```

Add Portuguese and additional Spanish keywords to the existing `FINANCIAL_KEYWORDS` list in `filter.py`:

```python
    # Portuguese (Brazilian banks)
    "transação", "transacao", "compra aprovada", "cartão", "cartao",
    "fatura", "pagamento", "pix",
    # Additional Spanish (CO/MX/PE)
    "movimiento", "consumo", "aviso", "alerta",
    "notificación", "notificacion",
```

- [ ] **Step 6: Run existing filter tests**

Run: `cd backend && python -m pytest tests/test_email_filter.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add backend/modules/email/bank_registry_service.py backend/tests/test_bank_registry_service.py backend/modules/email/filter.py
git commit -m "feat: add DB-backed bank registry service with Redis cache + Portuguese keywords"
```

---

## Task 4: LLM Parser — Confidence Waterfall

**Files:**
- Create: `backend/modules/email/llm_parser.py`
- Create: `backend/tests/test_llm_parser.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_llm_parser.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from modules.email.llm_parser import (
    parse_with_llm,
    _build_system_prompt,
    _parse_llm_response,
    WATERFALL_MODELS,
)
from modules.email.base import ParsedEmail


def test_waterfall_models_ordered_by_cost():
    """Models should be ordered cheapest to most expensive."""
    assert len(WATERFALL_MODELS) == 4
    assert WATERFALL_MODELS[0]["name"] == "gemini-3.1-flash-lite"
    assert WATERFALL_MODELS[-1]["name"] == "gemini-2.5-pro"


def test_build_system_prompt_includes_currency_rules():
    prompt = _build_system_prompt({"country": "CL", "bank_name": "Banco de Chile"})
    assert "CLP" in prompt
    assert "15990" in prompt  # example conversion


def test_build_system_prompt_includes_bank_context():
    prompt = _build_system_prompt({"country": "BR", "bank_name": "Nubank"})
    assert "BRL" in prompt
    assert "Nubank" in prompt


def test_parse_llm_response_valid_json():
    raw = '{"merchant":"LIDER","amount":15990,"currency":"CLP","transaction_date":"2026-04-05T14:32:00","transaction_type":"expense","transfer_recipient":null,"card_last_four":"4532","confidence":0.95}'
    result = _parse_llm_response(raw)
    assert result is not None
    assert result["merchant"] == "LIDER"
    assert result["amount"] == 15990
    assert result["confidence"] == 0.95


def test_parse_llm_response_with_code_fences():
    raw = '```json\n{"merchant":"LIDER","amount":15990,"currency":"CLP","transaction_date":"2026-04-05T14:32:00","transaction_type":"expense","transfer_recipient":null,"card_last_four":null,"confidence":0.9}\n```'
    result = _parse_llm_response(raw)
    assert result is not None
    assert result["merchant"] == "LIDER"


def test_parse_llm_response_missing_required_fields():
    raw = '{"merchant":"LIDER","confidence":0.9}'
    result = _parse_llm_response(raw)
    assert result is None  # missing amount, currency, date


def test_parse_llm_response_malformed_json():
    result = _parse_llm_response("not json at all")
    assert result is None


@pytest.mark.asyncio
async def test_parse_with_llm_returns_parsed_email():
    mock_response = MagicMock()
    mock_response.text = '{"merchant":"LIDER EXPRESS","amount":15990,"currency":"CLP","transaction_date":"2026-04-05T14:32:00","transaction_type":"expense","transfer_recipient":null,"card_last_four":"4532","confidence":0.95}'

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with patch("modules.email.llm_parser._get_client", return_value=mock_client):
        result, depth, model = await parse_with_llm(
            "Compra por $15.990 en LIDER EXPRESS",
            bank_metadata={"country": "CL", "bank_name": "Banco de Chile"},
        )

    assert isinstance(result, ParsedEmail)
    assert result.amount == 15990
    assert result.raw_merchant == "LIDER EXPRESS"
    assert result.confidence == 0.95
    assert depth == 1  # first model succeeded
    assert model == "gemini-3.1-flash-lite"


@pytest.mark.asyncio
async def test_parse_with_llm_escalates_on_low_confidence():
    low_conf_response = MagicMock()
    low_conf_response.text = '{"merchant":"LIDER","amount":15990,"currency":"CLP","transaction_date":"2026-04-05T14:32:00","transaction_type":"expense","transfer_recipient":null,"card_last_four":null,"confidence":0.7}'

    high_conf_response = MagicMock()
    high_conf_response.text = '{"merchant":"LIDER EXPRESS","amount":15990,"currency":"CLP","transaction_date":"2026-04-05T14:32:00","transaction_type":"expense","transfer_recipient":null,"card_last_four":"4532","confidence":0.9}'

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=[low_conf_response, high_conf_response]
    )

    with patch("modules.email.llm_parser._get_client", return_value=mock_client):
        result, depth, model = await parse_with_llm(
            "Compra por $15.990 en LIDER EXPRESS",
            bank_metadata={"country": "CL", "bank_name": "Banco de Chile"},
        )

    assert depth == 2  # escalated once
    assert model == "gemini-2.5-flash"
    assert result.raw_merchant == "LIDER EXPRESS"


@pytest.mark.asyncio
async def test_parse_with_llm_returns_none_on_total_failure():
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=Exception("API down"))

    with patch("modules.email.llm_parser._get_client", return_value=mock_client):
        result, depth, model = await parse_with_llm(
            "Some email text",
            bank_metadata={"country": "CL", "bank_name": "Banco de Chile"},
        )

    assert result is None
    assert depth == 4  # tried all models
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_llm_parser.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Implement LLM parser**

Create `backend/modules/email/llm_parser.py`:

```python
"""LLM-powered email parser with confidence-based model waterfall."""

import json
import logging
from datetime import datetime, timedelta

import google.genai as genai

from core.config import settings
from modules.email.base import ParsedEmail

logger = logging.getLogger(__name__)

_client = None

# Circuit breaker state (in-memory, resets on worker restart)
_error_count = 0
_total_count = 0
_circuit_open_until: datetime | None = None
_CIRCUIT_BREAKER_THRESHOLD = 0.5  # 50% error rate
_CIRCUIT_BREAKER_WINDOW = 20  # min calls before evaluating
_CIRCUIT_BREAKER_COOLDOWN = 900  # 15 minutes

WATERFALL_MODELS = [
    {"name": "gemini-3.1-flash-lite", "threshold": 0.9},
    {"name": "gemini-2.5-flash", "threshold": 0.8},
    {"name": "gemini-3-flash", "threshold": 0.7},
    {"name": "gemini-2.5-pro", "threshold": 0.0},  # accept any
]

_REQUIRED_FIELDS = {"merchant", "amount", "currency", "transaction_date", "transaction_type", "confidence"}


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def _build_system_prompt(bank_metadata: dict | None) -> str:
    country = bank_metadata.get("country", "CL") if bank_metadata else "CL"
    bank_name = bank_metadata.get("bank_name", "Unknown") if bank_metadata else "Unknown"

    currency_rules = {
        "CL": "CLP — return integer pesos, no subunits. Example: '$15.990' → 15990",
        "CO": "COP — return integer pesos, no subunits. Example: '$450.000' → 450000",
        "MX": "MXN — return integer centavos. Example: '$1,250.50' → 125050",
        "PE": "PEN — return integer centimos. Example: 'S/ 150.00' → 15000",
        "BR": "BRL — return integer centavos. Example: 'R$ 1.250,50' → 125050",
        "US": "USD — return integer cents. Example: '$17.08' → 1708",
    }
    currency_rule = currency_rules.get(country, currency_rules["US"])

    return f"""You are a financial email parser for {bank_name} ({country}).
Extract transaction data from bank notification emails.

CURRENCY RULE: {currency_rule}

Return ONLY valid JSON with this exact schema:
{{
  "merchant": "MERCHANT NAME",
  "amount": 15990,
  "currency": "CLP",
  "transaction_date": "2026-04-05T14:32:00",
  "transaction_type": "expense|transfer|income",
  "transfer_recipient": "NAME or null",
  "card_last_four": "4532 or null",
  "confidence": 0.95
}}

Rules:
- merchant: exact merchant/store name from the email, cleaned of location suffixes
- amount: integer in the smallest currency unit as specified above
- transaction_type: "expense" for purchases, "transfer" for transfers, "income" for deposits/inflows
- transfer_recipient: only if transaction_type is "transfer"
- confidence: 0.0 to 1.0 — how certain you are about the extraction accuracy
- If you cannot extract a required field, set confidence below 0.3
"""


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # remove opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def _parse_llm_response(raw_text: str) -> dict | None:
    """Parse LLM JSON response, return dict or None if invalid."""
    try:
        cleaned = _strip_code_fences(raw_text)
        data = json.loads(cleaned)
        if not _REQUIRED_FIELDS.issubset(data.keys()):
            return None
        return data
    except (json.JSONDecodeError, TypeError):
        return None


def _extraction_to_parsed_email(data: dict) -> ParsedEmail:
    """Convert LLM extraction dict to ParsedEmail dataclass."""
    tx_date = data["transaction_date"]
    if isinstance(tx_date, str):
        tx_date = datetime.fromisoformat(tx_date)

    return ParsedEmail(
        amount=int(data["amount"]),
        raw_merchant=data["merchant"],
        transaction_date=tx_date,
        bank_name="",  # filled by caller from bank_metadata
        transaction_type=data.get("transaction_type", "expense"),
        currency=data["currency"],
        transfer_recipient=data.get("transfer_recipient"),
        card_last_four=data.get("card_last_four"),
        confidence=data.get("confidence"),
    )


async def parse_with_llm(
    email_text: str,
    bank_metadata: dict | None = None,
) -> tuple[ParsedEmail | None, int, str | None]:
    """Parse email using LLM waterfall. Returns (ParsedEmail, depth, model_name).

    depth = how many models were tried (1 = first model succeeded)
    model_name = which model produced the result
    Returns (None, N, None) if all models fail.
    """
    global _error_count, _total_count, _circuit_open_until

    # Circuit breaker: skip LLM entirely if API is failing
    if _circuit_open_until and datetime.utcnow() < _circuit_open_until:
        logger.warning("Circuit breaker open — skipping LLM, falling back to regex")
        return None, 0, None

    thresholds = [float(t) for t in settings.llm_waterfall_thresholds.split(",")]
    system_prompt = _build_system_prompt(bank_metadata)
    client = _get_client()
    api_failed = False

    for i, model_cfg in enumerate(WATERFALL_MODELS):
        model_name = model_cfg["name"]
        threshold = thresholds[i] if i < len(thresholds) else model_cfg["threshold"]

        # Try with 1 retry on API error
        for attempt in range(2):
            try:
                response = await client.aio.models.generate_content(
                    model=model_name,
                    contents=email_text,
                    config=genai.types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.1,
                        max_output_tokens=512,
                    ),
                )
                data = _parse_llm_response(response.text)
                if data is None:
                    logger.warning("Malformed LLM response from %s, escalating", model_name)
                    break  # escalate to next model

                if data["confidence"] >= threshold:
                    parsed = _extraction_to_parsed_email(data)
                    return parsed, i + 1, model_name

                # Low confidence — escalate
                logger.info(
                    "Low confidence %.2f from %s (threshold %.2f), escalating",
                    data["confidence"], model_name, threshold,
                )
                break  # try next model

            except Exception as e:
                if attempt == 0:
                    logger.warning("API error from %s (attempt 1): %s, retrying", model_name, e)
                    continue
                logger.warning("API error from %s (attempt 2): %s, escalating", model_name, e)
                api_failed = True
                break

    # Update circuit breaker counters
    _total_count += 1
    if api_failed:
        _error_count += 1
    if _total_count >= _CIRCUIT_BREAKER_WINDOW:
        error_rate = _error_count / _total_count
        if error_rate >= _CIRCUIT_BREAKER_THRESHOLD:
            _circuit_open_until = datetime.utcnow() + timedelta(seconds=_CIRCUIT_BREAKER_COOLDOWN)
            logger.error("Circuit breaker OPEN — %.0f%% error rate, cooldown 15min", error_rate * 100)
        _error_count = 0
        _total_count = 0

    return None, len(WATERFALL_MODELS), None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_llm_parser.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/modules/email/llm_parser.py backend/tests/test_llm_parser.py
git commit -m "feat: add LLM email parser with confidence-based Gemini waterfall"
```

---

## Task 5: Template Executor — Declarative JSON Templates

**Files:**
- Create: `backend/modules/email/template_executor.py`
- Create: `backend/tests/test_template_executor.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_template_executor.py`:

```python
import pytest
from datetime import datetime
from modules.email.template_executor import execute_template
from modules.email.base import ParsedEmail


SAMPLE_HTML = """
<html><body>
<table>
  <tr><td class="merchant">LIDER EXPRESS</td></tr>
  <tr><td class="amount">$15.990</td></tr>
  <tr><td class="date">05/04/2026 14:32</td></tr>
</table>
</body></html>
"""

SAMPLE_TEMPLATE = {
    "bank_domain": "bancochile.cl",
    "version": 1,
    "selectors": {
        "amount": {
            "css": "td.amount",
            "regex": "\\$([\\d.]+)",
            "transform": "clp_integer",
        },
        "merchant": {
            "css": "td.merchant",
            "regex": None,
            "transform": "strip",
        },
        "date": {
            "css": "td.date",
            "regex": "(\\d{2}/\\d{2}/\\d{4}\\s+\\d{2}:\\d{2})",
            "transform": "parse_date_ddmmyyyy_hhmm",
        },
        "transaction_type": {
            "keywords_expense": ["compra", "cargo", "pago"],
            "keywords_transfer": ["transferencia"],
            "keywords_income": ["abono", "deposito"],
        },
    },
}


def test_execute_template_extracts_all_fields():
    result = execute_template(SAMPLE_HTML, SAMPLE_TEMPLATE, full_text="compra en LIDER")
    assert result is not None
    assert isinstance(result, ParsedEmail)
    assert result.amount == 15990
    assert result.raw_merchant == "LIDER EXPRESS"
    assert result.transaction_type == "expense"


def test_execute_template_clp_integer_transform():
    html = '<html><body><td class="amount">$1.250.000</td></body></html>'
    template = {
        "version": 1,
        "selectors": {
            "amount": {"css": "td.amount", "regex": "\\$([\\d.]+)", "transform": "clp_integer"},
            "merchant": {"css": None, "regex": None, "transform": "strip"},
            "date": {"css": None, "regex": None, "transform": "now"},
            "transaction_type": {"keywords_expense": [], "keywords_transfer": [], "keywords_income": []},
        },
    }
    result = execute_template(html, template, full_text="compra")
    assert result is not None
    assert result.amount == 1250000


def test_execute_template_usd_cents_transform():
    html = '<html><body><span class="amt">$17.08</span></body></html>'
    template = {
        "version": 1,
        "selectors": {
            "amount": {"css": "span.amt", "regex": "\\$([\\d,.]+)", "transform": "usd_cents"},
            "merchant": {"css": None, "regex": None, "transform": "strip"},
            "date": {"css": None, "regex": None, "transform": "now"},
            "transaction_type": {"keywords_expense": ["purchase"], "keywords_transfer": [], "keywords_income": []},
        },
    }
    result = execute_template(html, template, full_text="purchase at store")
    assert result is not None
    assert result.amount == 1708


def test_execute_template_returns_none_on_missing_amount():
    html = "<html><body>No amount here</body></html>"
    result = execute_template(html, SAMPLE_TEMPLATE, full_text="compra")
    assert result is None


def test_execute_template_returns_none_on_invalid_template():
    result = execute_template(SAMPLE_HTML, {"version": 1}, full_text="compra")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_template_executor.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Implement template executor**

Create `backend/modules/email/template_executor.py`:

```python
"""Execute declarative JSON extraction templates — no dynamic code, only fixed transforms."""

import logging
import re
from datetime import datetime

from bs4 import BeautifulSoup

from modules.email.base import ParsedEmail

logger = logging.getLogger(__name__)


# --- Fixed transform functions (auditable, no user input) ---

def _transform_strip(value: str) -> str:
    return value.strip()


def _transform_clp_integer(value: str) -> int:
    """'15.990' → 15990 (remove dots, no decimals)."""
    return int(value.replace(".", "").replace(",", ""))


def _transform_cop_integer(value: str) -> int:
    """'450.000' → 450000 (same as CLP — dots are thousands)."""
    return int(value.replace(".", "").replace(",", ""))


def _transform_usd_cents(value: str) -> int:
    """'17.08' → 1708, '2,000.00' → 200000."""
    cleaned = value.replace(",", "")
    return int(round(float(cleaned) * 100))


def _transform_mxn_cents(value: str) -> int:
    """'1,250.50' → 125050 (comma=thousands, dot=decimal)."""
    return _transform_usd_cents(value)


def _transform_brl_centavos(value: str) -> int:
    """'1.250,50' → 125050 (dot=thousands, comma=decimal)."""
    cleaned = value.replace(".", "").replace(",", ".")
    return int(round(float(cleaned) * 100))


def _transform_pen_centimos(value: str) -> int:
    """'150.00' → 15000."""
    return _transform_usd_cents(value)


def _transform_parse_date_ddmmyyyy_hhmm(value: str) -> datetime:
    return datetime.strptime(value.strip(), "%d/%m/%Y %H:%M")


def _transform_parse_date_ddmmyyyy(value: str) -> datetime:
    return datetime.strptime(value.strip(), "%d/%m/%Y")


def _transform_parse_date_mmddyy(value: str) -> datetime:
    return datetime.strptime(value.strip(), "%m/%d/%y")


def _transform_parse_date_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.strip())


def _transform_now(_: str) -> datetime:
    return datetime.utcnow()


TRANSFORMS: dict[str, callable] = {
    "strip": _transform_strip,
    "clp_integer": _transform_clp_integer,
    "cop_integer": _transform_cop_integer,
    "usd_cents": _transform_usd_cents,
    "mxn_cents": _transform_mxn_cents,
    "brl_centavos": _transform_brl_centavos,
    "pen_centimos": _transform_pen_centimos,
    "parse_date_ddmmyyyy_hhmm": _transform_parse_date_ddmmyyyy_hhmm,
    "parse_date_ddmmyyyy": _transform_parse_date_ddmmyyyy,
    "parse_date_mmddyy": _transform_parse_date_mmddyy,
    "parse_date_iso": _transform_parse_date_iso,
    "now": _transform_now,
}


def _extract_field(html_soup: BeautifulSoup, full_text: str, selector_cfg: dict) -> str | None:
    """Extract a field using CSS selector + regex from template config."""
    raw = None

    # CSS selector
    css = selector_cfg.get("css")
    if css:
        el = html_soup.select_one(css)
        if el:
            raw = el.get_text(strip=True)

    # Fallback to full text if no CSS match
    if raw is None and selector_cfg.get("regex"):
        match = re.search(selector_cfg["regex"], full_text)
        if match:
            raw = match.group(1) if match.groups() else match.group(0)

    # Apply regex to CSS-extracted text
    if raw and selector_cfg.get("regex") and css:
        match = re.search(selector_cfg["regex"], raw)
        if match:
            raw = match.group(1) if match.groups() else match.group(0)

    return raw


def _detect_transaction_type(full_text: str, type_cfg: dict) -> str:
    """Detect transaction type from keywords."""
    text_lower = full_text.lower()
    for kw in type_cfg.get("keywords_transfer", []):
        if kw in text_lower:
            return "transfer"
    for kw in type_cfg.get("keywords_income", []):
        if kw in text_lower:
            return "income"
    for kw in type_cfg.get("keywords_expense", []):
        if kw in text_lower:
            return "expense"
    return "expense"  # default


def execute_template(
    html: str, template: dict, *, full_text: str = ""
) -> ParsedEmail | None:
    """Execute a declarative extraction template. Returns ParsedEmail or None."""
    try:
        selectors = template.get("selectors")
        if not selectors:
            return None

        soup = BeautifulSoup(html, "html.parser")
        if not full_text:
            full_text = soup.get_text()

        # Extract amount
        amount_cfg = selectors.get("amount", {})
        amount_raw = _extract_field(soup, full_text, amount_cfg)
        if not amount_raw:
            return None
        transform_name = amount_cfg.get("transform", "strip")
        if transform_name not in TRANSFORMS:
            return None
        amount = TRANSFORMS[transform_name](amount_raw)

        # Extract merchant
        merchant_cfg = selectors.get("merchant", {})
        merchant_raw = _extract_field(soup, full_text, merchant_cfg)
        merchant = TRANSFORMS.get(
            merchant_cfg.get("transform", "strip"), _transform_strip
        )(merchant_raw) if merchant_raw else None

        # Extract date
        date_cfg = selectors.get("date", {})
        date_raw = _extract_field(soup, full_text, date_cfg)
        date_transform = date_cfg.get("transform", "now")
        if date_raw and date_transform in TRANSFORMS:
            tx_date = TRANSFORMS[date_transform](date_raw)
        else:
            tx_date = datetime.utcnow()

        # Detect transaction type
        type_cfg = selectors.get("transaction_type", {})
        tx_type = _detect_transaction_type(full_text, type_cfg)

        return ParsedEmail(
            amount=int(amount),
            raw_merchant=merchant or "Unknown",
            transaction_date=tx_date,
            bank_name="",  # filled by caller
            transaction_type=tx_type,
            currency=template.get("currency", "CLP"),
        )

    except Exception as e:
        logger.warning("Template execution failed: %s", e)
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_template_executor.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/modules/email/template_executor.py backend/tests/test_template_executor.py
git commit -m "feat: add declarative JSON template executor with fixed transforms"
```

---

## Task 6: Orchestrator — Wire Template + LLM + Regex Together

**Files:**
- Modify: `backend/modules/email/parser.py`
- Create: `backend/tests/test_parser_orchestrator.py`

- [ ] **Step 1: Write failing tests for orchestrator**

Create `backend/tests/test_parser_orchestrator.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from modules.email.base import ParsedEmail
from modules.email.parser import parse_bank_email


@pytest.mark.asyncio
async def test_parse_uses_template_when_available():
    """When bank has an active template and it succeeds, use template result."""
    template_result = ParsedEmail(
        amount=15990, raw_merchant="LIDER", transaction_date=datetime(2026, 4, 5),
        bank_name="Banco de Chile", currency="CLP",
    )
    bank_meta = {"active_template_id": "abc-123", "bank_name": "Banco de Chile", "country": "CL"}

    with patch("modules.email.parser._get_active_template", new_callable=AsyncMock, return_value={"selectors": {}}), \
         patch("modules.email.parser.execute_template", return_value=template_result):
        result, parser_used, depth, model = await parse_bank_email(
            "<html>email</html>", "stripped text", bank_metadata=bank_meta
        )

    assert result == template_result
    assert parser_used == "template"
    assert depth is None


@pytest.mark.asyncio
async def test_parse_falls_through_to_llm_when_no_template():
    """When bank has no active template, use LLM."""
    llm_result = ParsedEmail(
        amount=15990, raw_merchant="LIDER", transaction_date=datetime(2026, 4, 5),
        bank_name="", currency="CLP", confidence=0.95,
    )
    bank_meta = {"active_template_id": None, "bank_name": "Banco de Chile", "country": "CL"}

    with patch("modules.email.parser.parse_with_llm", new_callable=AsyncMock, return_value=(llm_result, 1, "gemini-3.1-flash-lite")):
        result, parser_used, depth, model = await parse_bank_email(
            "<html>email</html>", "stripped text", bank_metadata=bank_meta
        )

    assert result == llm_result
    assert parser_used == "llm"
    assert depth == 1
    assert model == "gemini-3.1-flash-lite"


@pytest.mark.asyncio
async def test_parse_falls_through_to_regex_when_llm_fails():
    """When LLM returns None, fall back to regex."""
    regex_result = ParsedEmail(
        amount=15990, raw_merchant="LIDER", transaction_date=datetime(2026, 4, 5),
        bank_name="Banco de Chile", currency="CLP",
    )
    bank_meta = {"active_template_id": None, "bank_name": "Banco de Chile", "country": "CL"}

    with patch("modules.email.parser.parse_with_llm", new_callable=AsyncMock, return_value=(None, 4, None)), \
         patch("modules.email.parser.parse_bank_email_regex", return_value=regex_result):
        result, parser_used, depth, model = await parse_bank_email(
            "<html>email</html>", "stripped text", bank_metadata=bank_meta
        )

    assert result == regex_result
    assert parser_used == "regex"


@pytest.mark.asyncio
async def test_parse_template_failure_falls_through_to_llm():
    """When template execution returns None, fall through to LLM."""
    llm_result = ParsedEmail(
        amount=15990, raw_merchant="LIDER", transaction_date=datetime(2026, 4, 5),
        bank_name="", currency="CLP", confidence=0.9,
    )
    bank_meta = {"active_template_id": "abc-123", "bank_name": "Banco de Chile", "country": "CL"}

    with patch("modules.email.parser._get_active_template", new_callable=AsyncMock, return_value={"selectors": {}}), \
         patch("modules.email.parser.execute_template", return_value=None), \
         patch("modules.email.parser.parse_with_llm", new_callable=AsyncMock, return_value=(llm_result, 1, "gemini-3.1-flash-lite")):
        result, parser_used, depth, model = await parse_bank_email(
            "<html>email</html>", "stripped text", bank_metadata=bank_meta
        )

    assert parser_used == "llm"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_parser_orchestrator.py -v`
Expected: FAIL

- [ ] **Step 3: Refactor parser.py — rename existing function, add orchestrator**

In `backend/modules/email/parser.py`:

1. **IMPORTANT:** First grep the codebase for all callers of `parse_bank_email`, `is_bank_sender`, and `get_bank_name`. Update any callers beyond `tasks.py` (check `backend/scripts/*.py`). Scripts that use the sync versions should import from `filter.py` (kept as sync fallback) or be updated to use the async service.
2. Rename `parse_bank_email` → `parse_bank_email_regex` (keep all existing logic)
3. Add new async `parse_bank_email` orchestrator at the end of the file:

```python
# Add imports at top of file:
import logging
from modules.email.llm_parser import parse_with_llm
from modules.email.template_executor import execute_template

logger = logging.getLogger(__name__)


async def _get_active_template(template_id: str, *, db=None) -> dict | None:
    """Fetch active template JSON from DB."""
    if not template_id or not db:
        return None
    from sqlalchemy import select
    from modules.email.models import EmailTemplate
    stmt = select(EmailTemplate).where(
        EmailTemplate.id == template_id,
        EmailTemplate.status == "active",
    )
    result = await db.execute(stmt)
    entry = result.scalar_one_or_none()
    return entry.template_code if entry else None


async def parse_bank_email(
    raw_html: str,
    stripped_text: str,
    *,
    bank_metadata: dict | None = None,
    db=None,
) -> tuple[ParsedEmail | None, str, int | None, str | None]:
    """Three-layer parser: template → LLM waterfall → regex fallback.

    Returns (ParsedEmail | None, parser_used, waterfall_depth, model_name).
    parser_used: "template" | "llm" | "regex"
    """
    # Layer 1: Template
    template_id = (bank_metadata or {}).get("active_template_id")
    if template_id:
        template = await _get_active_template(template_id, db=db)
        if template:
            result = execute_template(raw_html, template, full_text=stripped_text)
            if result:
                if bank_metadata:
                    result.bank_name = bank_metadata.get("bank_name", "")
                return result, "template", None, None

    # Layer 2: LLM waterfall
    result, depth, model = await parse_with_llm(stripped_text, bank_metadata=bank_metadata)
    if result:
        if bank_metadata:
            result.bank_name = bank_metadata.get("bank_name", "")
        return result, "llm", depth, model

    # Layer 3: Legacy regex fallback
    result = parse_bank_email_regex(stripped_text)
    if result:
        return result, "regex", None, None

    return None, "regex", None, None
```

- [ ] **Step 4: Run all parser tests**

Run: `cd backend && python -m pytest tests/test_parser_orchestrator.py tests/test_email_parser.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/modules/email/parser.py backend/tests/test_parser_orchestrator.py
git commit -m "feat: add three-layer parser orchestrator (template → LLM → regex)"
```

---

## Task 7: Integrate into process_email Job + Logging

**Files:**
- Modify: `backend/jobs/tasks.py`

- [ ] **Step 1: Update process_email to use new parser and log results**

In `backend/jobs/tasks.py`, make these changes:

1. Add imports at top:

```python
from modules.email.bank_registry_service import (
    is_bank_sender as is_bank_sender_async,
    get_bank_name as get_bank_name_async,
    get_bank_metadata,
    is_financial_email,
)
from modules.email.parser import parse_bank_email  # now async orchestrator
from modules.email.parser import _strip_html
from modules.email.models import ParsedEmailLog
```

2. In the email processing loop (where `is_bank_sender` and `parse_bank_email` are called), replace the sync calls with async:

```python
# Replace: if not is_bank_sender(raw_email.sender):
if not await is_bank_sender_async(raw_email.sender, redis=redis_client, db=db):
    continue

# Replace: if not is_financial_email(raw_email.subject, raw_email.sender, raw_email.body):
if not is_financial_email(raw_email.subject, raw_email.sender, raw_email.body):
    continue

# Get bank metadata for LLM context
bank_meta = await get_bank_metadata(raw_email.sender, redis=redis_client, db=db)

# Replace: parsed = parse_bank_email(stripped_text)
stripped = _strip_html(raw_email.body)
parsed, parser_used, depth, model_used = await parse_bank_email(
    raw_email.body, stripped, bank_metadata=bank_meta, db=db,
)

# Replace: inferred_bank = get_bank_name(raw_email.sender)
inferred_bank = bank_meta["bank_name"] if bank_meta else "Unknown"
```

3. After transaction creation, log to `parsed_email_log`:

```python
# Log parsing result
log_entry = ParsedEmailLog(
    user_id=user.id,
    bank_domain=bank_meta["bank_domain"] if bank_meta else "unknown",
    country=bank_meta["country"] if bank_meta else None,
    raw_email_html=raw_email.body,  # stored for all paths — needed for shadow validation + template training
    llm_extraction={
        "merchant": parsed.raw_merchant,
        "amount": parsed.amount,
        "currency": parsed.currency,
        "date": str(parsed.transaction_date),
        "type": parsed.transaction_type,
        "confidence": parsed.confidence,
    } if parser_used == "llm" else None,
    parser_used=parser_used,
    llm_model_used=model_used,
    waterfall_depth=depth,
)
db.add(log_entry)
```

- [ ] **Step 2: Add purge_email_logs job**

Add to `backend/jobs/tasks.py`:

```python
async def purge_email_logs(ctx: dict) -> None:
    """Purge raw_email_html from parsed_email_log older than 7 days."""
    async with get_db_session() as db:
        from sqlalchemy import update, text
        from modules.email.models import ParsedEmailLog
        cutoff = datetime.utcnow() - timedelta(days=7)
        stmt = (
            update(ParsedEmailLog)
            .where(ParsedEmailLog.created_at < cutoff)
            .where(ParsedEmailLog.raw_email_html.isnot(None))
            .values(raw_email_html=None)
        )
        result = await db.execute(stmt)
        await db.commit()
        logger.info("Purged raw HTML from %d email log entries", result.rowcount)
```

- [ ] **Step 3: Run existing email processing tests**

Run: `cd backend && python -m pytest tests/test_email_parser.py tests/test_email_filter.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add backend/jobs/tasks.py
git commit -m "feat: integrate LLM parser into process_email job + add parsed_email_log writing"
```

---

## Task 8: Template Agent — Autonomous Pattern Learning

**Files:**
- Create: `backend/modules/email/template_agent.py`
- Create: `backend/tests/test_template_agent.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_template_agent.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from modules.email.template_agent import (
    discover_candidate_banks,
    validate_template,
    should_retire_template,
)


@pytest.mark.asyncio
async def test_discover_candidate_banks_finds_eligible():
    """Banks with 20+ total emails and 5+ recent should be candidates."""
    mock_db = AsyncMock()
    # Simulate query result: bank_domain, total_count, recent_count
    mock_result = MagicMock()
    mock_result.all.return_value = [
        ("bancochile.cl", 25, 8),
        ("santander.cl", 30, 6),
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    candidates = await discover_candidate_banks(db=mock_db)
    assert len(candidates) == 2
    assert "bancochile.cl" in [c[0] for c in candidates]


@pytest.mark.asyncio
async def test_discover_candidate_banks_excludes_low_count():
    """Banks with <20 total emails should be excluded."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [
        ("newbank.cl", 5, 3),
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    candidates = await discover_candidate_banks(db=mock_db)
    assert len(candidates) == 0


def test_validate_template_passes_with_perfect_accuracy():
    """Template that matches all LLM extractions should pass."""
    template_results = [
        {"amount": 15990, "merchant": "LIDER"},
        {"amount": 8500, "merchant": "COPEC"},
    ]
    llm_results = [
        {"amount": 15990, "merchant": "LIDER"},
        {"amount": 8500, "merchant": "COPEC"},
    ]
    passed, accuracy = validate_template(template_results, llm_results)
    assert passed is True
    assert accuracy == 1.0


def test_validate_template_fails_on_amount_mismatch():
    """Any amount mismatch should fail validation."""
    template_results = [
        {"amount": 15990, "merchant": "LIDER"},
        {"amount": 8501, "merchant": "COPEC"},  # off by 1
    ]
    llm_results = [
        {"amount": 15990, "merchant": "LIDER"},
        {"amount": 8500, "merchant": "COPEC"},
    ]
    passed, accuracy = validate_template(template_results, llm_results)
    assert passed is False


def test_should_retire_template_on_amount_drift():
    """Any amount mismatch in shadow validation should trigger retirement."""
    shadow_results = [
        {"shadow_match": True, "amount_match": True},
        {"shadow_match": True, "amount_match": False},  # amount drift!
        {"shadow_match": True, "amount_match": True},
    ]
    assert should_retire_template(shadow_results) is True


def test_should_not_retire_template_on_good_shadow():
    shadow_results = [
        {"shadow_match": True, "amount_match": True},
        {"shadow_match": True, "amount_match": True},
    ]
    assert should_retire_template(shadow_results) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_template_agent.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Implement Template Agent**

Create `backend/modules/email/template_agent.py`:

```python
"""Autonomous Template Agent — discovers, generates, validates, promotes, and retires templates."""

import hashlib
import json
import logging
import random
from datetime import datetime, timedelta

import google.genai as genai
from sqlalchemy import select, func, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from modules.email.models import EmailTemplate, ParsedEmailLog, BankRegistry
from modules.email.template_executor import execute_template
from modules.email.llm_parser import parse_with_llm

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


async def discover_candidate_banks(*, db: AsyncSession) -> list[tuple[str, int, int]]:
    """Find banks with enough LLM-parsed emails but no active template.

    Returns: [(bank_domain, total_count, recent_count), ...]
    """
    min_total = settings.template_agent_min_emails
    min_recent = settings.template_agent_recency_min
    recency_days = settings.template_agent_recency_days
    cutoff = datetime.utcnow() - timedelta(days=recency_days)

    # Banks with active templates — exclude
    active_stmt = select(BankRegistry.bank_domain).where(
        BankRegistry.active_template_id.isnot(None)
    )
    active_result = await db.execute(active_stmt)
    active_domains = {row[0] for row in active_result.all()}

    # Aggregate email counts by bank
    stmt = (
        select(
            ParsedEmailLog.bank_domain,
            func.count().label("total_count"),
            func.count().filter(ParsedEmailLog.created_at >= cutoff).label("recent_count"),
        )
        .where(ParsedEmailLog.parser_used == "llm")
        .where(ParsedEmailLog.raw_email_html.isnot(None))
        .group_by(ParsedEmailLog.bank_domain)
    )
    result = await db.execute(stmt)
    rows = result.all()

    candidates = []
    for domain, total, recent in rows:
        if domain in active_domains:
            continue
        if total >= min_total and recent >= min_recent:
            candidates.append((domain, total, recent))

    return candidates


async def generate_template_json(
    samples: list[dict], *, bank_domain: str
) -> dict | None:
    """Use LLM to generate a declarative extraction template from samples.

    samples: [{html: str, extraction: dict}, ...]
    Returns: template JSON dict or None.
    """
    prompt = f"""You are a bank email template generator for {bank_domain}.

Given these sample bank notification emails and their correct field extractions,
generate a declarative JSON extraction template.

The template must use this exact schema:
{{
  "bank_domain": "{bank_domain}",
  "version": 1,
  "currency": "CLP",
  "selectors": {{
    "amount": {{
      "css": "CSS selector or null",
      "regex": "regex pattern with capture group or null",
      "transform": "one of: clp_integer, cop_integer, usd_cents, mxn_cents, brl_centavos, pen_centimos"
    }},
    "merchant": {{
      "css": "CSS selector or null",
      "regex": "regex pattern or null",
      "transform": "strip"
    }},
    "date": {{
      "css": "CSS selector or null",
      "regex": "regex pattern or null",
      "transform": "one of: parse_date_ddmmyyyy_hhmm, parse_date_ddmmyyyy, parse_date_mmddyy, parse_date_iso, now"
    }},
    "transaction_type": {{
      "keywords_expense": ["list", "of", "keywords"],
      "keywords_transfer": ["list"],
      "keywords_income": ["list"]
    }}
  }}
}}

IMPORTANT: Only use the transforms listed above. CSS selectors should target the most specific element possible. Regex patterns should have a capture group for the value.

Return ONLY the JSON template, no explanation.

SAMPLES:
"""

    for i, s in enumerate(samples[:10]):
        prompt += f"\n--- Sample {i+1} ---\nHTML:\n{s['html'][:2000]}\n\nCorrect extraction:\n{json.dumps(s['extraction'])}\n"

    try:
        response = await _get_client().aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=2048,
            ),
        )
        text = response.text.strip()
        if text.startswith("```"):
            lines = text.split("\n")[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return json.loads(text)
    except Exception as e:
        logger.error("Template generation failed for %s: %s", bank_domain, e)
        return None


def validate_template(
    template_results: list[dict], llm_results: list[dict]
) -> tuple[bool, float]:
    """Validate template extractions against LLM ground truth.

    Returns: (passed, accuracy).
    Requires 100% amount match, 95% merchant match.
    """
    if not template_results or len(template_results) != len(llm_results):
        return False, 0.0

    amount_matches = 0
    merchant_matches = 0
    total = len(template_results)

    for t, l in zip(template_results, llm_results):
        if t.get("amount") == l.get("amount"):
            amount_matches += 1
        t_merchant = (t.get("merchant") or "").strip().upper()
        l_merchant = (l.get("merchant") or "").strip().upper()
        if t_merchant == l_merchant or (t_merchant and l_merchant and t_merchant in l_merchant):
            merchant_matches += 1

    if amount_matches < total:  # 100% amount match required
        return False, amount_matches / total

    merchant_accuracy = merchant_matches / total
    overall = (amount_matches + merchant_matches) / (total * 2)
    return merchant_accuracy >= 0.95, overall


def should_retire_template(shadow_results: list[dict]) -> bool:
    """Check if template should be retired based on shadow validation results.

    ANY amount mismatch → retire immediately.
    """
    for r in shadow_results:
        if not r.get("amount_match", True):
            return True
    return False


async def promote_template(
    template_id, bank_domain: str, *, db: AsyncSession
) -> None:
    """Promote template to active, update bank_registry."""
    await db.execute(
        update(EmailTemplate)
        .where(EmailTemplate.id == template_id)
        .values(status="active", promoted_at=datetime.utcnow())
    )
    await db.execute(
        update(BankRegistry)
        .where(BankRegistry.bank_domain == bank_domain)
        .values(active_template_id=template_id)
    )
    await db.commit()
    logger.info("Promoted template %s for %s", template_id, bank_domain)


async def retire_template(
    template_id, bank_domain: str, reason: str, *, db: AsyncSession
) -> None:
    """Retire template, clear from bank_registry, alert admin."""
    await db.execute(
        update(EmailTemplate)
        .where(EmailTemplate.id == template_id)
        .values(status="retired", retired_at=datetime.utcnow(), retired_reason=reason)
    )
    await db.execute(
        update(BankRegistry)
        .where(BankRegistry.bank_domain == bank_domain)
        .values(active_template_id=None)
    )
    await db.commit()
    logger.warning("Retired template %s for %s: %s", template_id, bank_domain, reason)
    # TODO: Send WhatsApp alert to admin


async def run_shadow_validation(*, db: AsyncSession) -> None:
    """Run shadow validation on active templates — compare template vs LLM on sample."""
    rate = settings.llm_shadow_validation_rate

    # Get all banks with active templates
    stmt = select(BankRegistry).where(BankRegistry.active_template_id.isnot(None))
    result = await db.execute(stmt)
    banks = result.scalars().all()

    for bank in banks:
        # Get recent template-parsed emails
        cutoff = datetime.utcnow() - timedelta(days=1)
        log_stmt = (
            select(ParsedEmailLog)
            .where(
                and_(
                    ParsedEmailLog.bank_domain == bank.bank_domain,
                    ParsedEmailLog.parser_used == "template",
                    ParsedEmailLog.created_at >= cutoff,
                    ParsedEmailLog.shadow_match.is_(None),
                )
            )
        )
        log_result = await db.execute(log_stmt)
        logs = log_result.scalars().all()

        # Sample at configured rate
        sample = [l for l in logs if random.random() < rate]
        if not sample:
            continue

        shadow_results = []
        for log_entry in sample:
            if not log_entry.raw_email_html:
                continue

            # Run LLM on the same email
            llm_parsed, _, _ = await parse_with_llm(
                log_entry.raw_email_html,
                bank_metadata={"country": bank.country, "bank_name": bank.bank_name},
            )
            if not llm_parsed:
                continue

            template_data = log_entry.template_extraction or {}
            amount_match = template_data.get("amount") == llm_parsed.amount
            shadow_results.append({"shadow_match": True, "amount_match": amount_match})

            # Update log entry
            log_entry.shadow_match = amount_match
            log_entry.llm_extraction = {
                "merchant": llm_parsed.raw_merchant,
                "amount": llm_parsed.amount,
                "currency": llm_parsed.currency,
            }

        if shadow_results and should_retire_template(shadow_results):
            await retire_template(
                bank.active_template_id,
                bank.bank_domain,
                f"Shadow validation drift: amount mismatch in {len(shadow_results)} samples",
                db=db,
            )

    await db.commit()


async def run_template_agent(ctx: dict) -> None:
    """Main entry point — runs daily as ARQ cron job."""
    from core.database import get_db_session

    async with get_db_session() as db:
        # Phase 1: Shadow validation on existing templates
        await run_shadow_validation(db=db)

        # Phase 2: Discover candidates for new templates
        candidates = await discover_candidate_banks(db=db)
        logger.info("Template agent found %d candidate banks", len(candidates))

        for bank_domain, total_count, recent_count in candidates:
            # Fetch sample emails
            stmt = (
                select(ParsedEmailLog)
                .where(
                    and_(
                        ParsedEmailLog.bank_domain == bank_domain,
                        ParsedEmailLog.parser_used == "llm",
                        ParsedEmailLog.raw_email_html.isnot(None),
                        ParsedEmailLog.llm_extraction.isnot(None),
                    )
                )
                .order_by(ParsedEmailLog.created_at.desc())
                .limit(20)
            )
            result = await db.execute(stmt)
            logs = result.scalars().all()

            if len(logs) < 10:
                continue

            samples = [
                {"html": l.raw_email_html, "extraction": l.llm_extraction}
                for l in logs
            ]

            # Generate template
            template_json = await generate_template_json(samples, bank_domain=bank_domain)
            if not template_json:
                continue

            # Validate: run template on all samples, compare to LLM
            template_results = []
            llm_results = []
            for s in samples:
                t_result = execute_template(s["html"], template_json, full_text="")
                if t_result:
                    template_results.append({"amount": t_result.amount, "merchant": t_result.raw_merchant})
                    llm_results.append({"amount": s["extraction"]["amount"], "merchant": s["extraction"]["merchant"]})

            if len(template_results) < len(samples) * 0.8:
                logger.info("Template for %s failed: too many extraction failures", bank_domain)
                continue

            passed, accuracy = validate_template(template_results, llm_results)
            if not passed:
                logger.info("Template for %s failed validation (accuracy: %.2f)", bank_domain, accuracy)
                continue

            # Store and promote
            template_hash = hashlib.sha256(json.dumps(template_json, sort_keys=True).encode()).hexdigest()
            new_template = EmailTemplate(
                bank_domain=bank_domain,
                country=logs[0].country or "",
                template_code=template_json,
                template_hash=template_hash,
                status="candidate",
                validated_count=len(template_results),
                accuracy=accuracy,
            )
            db.add(new_template)
            await db.flush()
            await promote_template(new_template.id, bank_domain, db=db)

        logger.info("Template agent run complete")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_template_agent.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/modules/email/template_agent.py backend/tests/test_template_agent.py
git commit -m "feat: add autonomous Template Agent — discover, generate, validate, promote, retire"
```

---

## Task 9: Wire Worker Cron Jobs

**Files:**
- Modify: `backend/worker.py`
- Modify: `backend/jobs/tasks.py` (import the new jobs)

- [ ] **Step 1: Add imports to tasks.py**

At the top of `backend/jobs/tasks.py`, add:

```python
from modules.email.template_agent import run_template_agent
```

Ensure `purge_email_logs` (added in Task 7) is also importable.

- [ ] **Step 2: Update worker.py**

In `backend/worker.py`:

1. Add imports:

```python
from jobs.tasks import (
    # ... existing imports ...
    purge_email_logs,
)
from modules.email.template_agent import run_template_agent
```

2. Add to `FastWorkerSettings.cron_jobs`:

```python
cron(purge_email_logs, hour=3, minute=30),  # 3:30am daily — purge 7-day old HTML
```

3. Add to `SlowWorkerSettings`:

```python
# In functions list:
functions = [
    run_connect_sync,
    run_plaid_sync_job,
    process_merchant_review,
    run_template_agent,  # NEW
]

# In cron_jobs:
cron_jobs = [
    cron(run_reconciliation_job, hour=6, minute=0),  # 6am daily
    cron(run_template_agent, hour=2, minute=0),  # 2am daily — template generation
]
```

- [ ] **Step 3: Verify worker module loads**

Run: `cd backend && python -c "from worker import FastWorkerSettings, SlowWorkerSettings; print('Fast crons:', len(FastWorkerSettings.cron_jobs)); print('Slow crons:', len(SlowWorkerSettings.cron_jobs))"`
Expected: Fast crons: 7, Slow crons: 2

- [ ] **Step 4: Commit**

```bash
git add backend/worker.py backend/jobs/tasks.py
git commit -m "feat: wire template_agent cron (2am daily) + purge_email_logs (3:30am daily)"
```

---

## Task 10: Integration Test — Full Pipeline End-to-End

**Files:**
- Create: `backend/tests/test_llm_parser_integration.py`

- [ ] **Step 1: Write integration test**

Create `backend/tests/test_llm_parser_integration.py`:

```python
"""Integration test: email → parse (all 3 layers) → ParsedEmail."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from modules.email.parser import parse_bank_email, parse_bank_email_regex, _strip_html
from modules.email.base import ParsedEmail


# Real Banco de Chile email sample (from existing test fixtures)
BANCO_CHILE_EMAIL = """Te informamos que se ha realizado una compra por $15.990 con Tarjeta de Credito ****5032 en LIDER EXPRESS SANTIAGO CL el 05/04/2026 14:32."""


@pytest.mark.asyncio
async def test_full_pipeline_llm_path():
    """Email with no template → LLM parses → ParsedEmail returned."""
    llm_result = ParsedEmail(
        amount=15990, raw_merchant="LIDER EXPRESS", transaction_date=datetime(2026, 4, 5, 14, 32),
        bank_name="", currency="CLP", confidence=0.95,
    )
    bank_meta = {"active_template_id": None, "bank_name": "Banco de Chile", "country": "CL"}

    with patch("modules.email.parser.parse_with_llm", new_callable=AsyncMock, return_value=(llm_result, 1, "gemini-3.1-flash-lite")):
        result, parser_used, depth, model = await parse_bank_email(
            BANCO_CHILE_EMAIL, BANCO_CHILE_EMAIL, bank_metadata=bank_meta,
        )

    assert result is not None
    assert result.amount == 15990
    assert result.raw_merchant == "LIDER EXPRESS"
    assert parser_used == "llm"
    assert result.bank_name == "Banco de Chile"


@pytest.mark.asyncio
async def test_full_pipeline_regex_fallback():
    """When LLM fails, regex fallback should still work for known formats."""
    bank_meta = {"active_template_id": None, "bank_name": "Banco de Chile", "country": "CL"}

    with patch("modules.email.parser.parse_with_llm", new_callable=AsyncMock, return_value=(None, 4, None)):
        result, parser_used, depth, model = await parse_bank_email(
            BANCO_CHILE_EMAIL, BANCO_CHILE_EMAIL, bank_metadata=bank_meta,
        )

    assert result is not None
    assert parser_used == "regex"
    assert result.amount == 15990


def test_regex_parser_still_works_standalone():
    """Renamed regex parser should still work for existing bank formats."""
    result = parse_bank_email_regex(BANCO_CHILE_EMAIL)
    assert result is not None
    assert result.amount == 15990
    assert "LIDER" in result.raw_merchant
```

- [ ] **Step 2: Run integration tests**

Run: `cd backend && python -m pytest tests/test_llm_parser_integration.py -v`
Expected: All PASS

- [ ] **Step 3: Run full test suite**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: All existing + new tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_llm_parser_integration.py
git commit -m "test: add integration tests for three-layer parser pipeline"
```

---

## Task 11: Final Cleanup + Push

- [ ] **Step 1: Run full test suite one more time**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 2: Push all commits**

```bash
git push
```

- [ ] **Step 3: Update NEXT-STEPS.md**

Remove the LLM parser from pending work, add post-launch monitoring items:
- Monitor waterfall depth distribution after first 1K transactions
- Calibrate confidence thresholds after first month of data
- Review Template Agent promotions after first active template

---

## Summary

| Task | What it builds | Tests |
|------|---------------|-------|
| 1 | DB tables + migration + seed data | Migration compiles |
| 2 | ParsedEmail extension + config | Existing tests pass |
| 3 | Bank registry service (replaces hardcoded domains) | 9 tests |
| 4 | LLM parser with confidence waterfall | 8 tests |
| 5 | Declarative template executor | 5 tests |
| 6 | Three-layer orchestrator | 4 tests |
| 7 | process_email integration + logging | Existing tests pass |
| 8 | Autonomous Template Agent | 5 tests |
| 9 | Worker cron jobs wiring | Module load check |
| 10 | End-to-end integration tests | 3 tests |
| 11 | Cleanup + push | Full suite passes |
