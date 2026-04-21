"""Tests for Task 2.7: persist card_last_four from email parsing and
eagerly resolve transfer_to_account_id at ingest time.

Covers:
1. Regex parser extracts card_last_four from CC-payment body
2. LLM parser threads card_last_four onto ParsedEmail
3. Ingest helper persists card_last_four and resolves transfer_to_account_id
   when a household BankAccount.account_number matches
4. Ingest helper leaves transfer_to_account_id null when no match
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Register every model so Base.metadata resolves FKs on flush.
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember


# ---------------------------------------------------------------------------
# 1. Regex parser
# ---------------------------------------------------------------------------


def test_regex_parser_extracts_card_last_four_from_cc_payment_body():
    """Regex parser must capture ****3100 from a CC-payment email body."""
    from modules.email.parser import parse_bank_email_regex

    body = (
        "Comprobante de pago exitoso Detalle cuenta(s) pagada(s) "
        "Comercio Banco de Chile Monto $ 250.000 Detalle del pago "
        "Medio de pago pago a la tarjeta de crédito Visa Signature "
        "Titular terminación ****3100 por un monto de $250.000 "
        "Fecha y Hora 13/03/2026 09:45:03"
    )

    result = parse_bank_email_regex(body)
    assert result is not None
    assert result.transaction_type == "transfer"
    assert result.card_last_four == "3100"
    assert "3100" in result.raw_merchant


def test_regex_parser_leaves_card_last_four_null_on_non_cc_email():
    """Non-CC emails (plain purchases) should have card_last_four = None."""
    from modules.email.parser import parse_bank_email_regex

    body = "Se ha realizado una COMPRA por $15.990 en LIDER PROVI " "Fecha: 10/03/2026 14:32"
    result = parse_bank_email_regex(body)
    assert result is not None
    assert result.card_last_four is None


# ---------------------------------------------------------------------------
# 2. LLM parser
# ---------------------------------------------------------------------------


def _make_mock_response(data: dict) -> MagicMock:
    mock = MagicMock()
    mock.text = json.dumps(data)
    return mock


@pytest.mark.asyncio
async def test_llm_parser_threads_card_last_four_to_parsed_email():
    """LLM parser must propagate card_last_four from the JSON response
    onto the returned ParsedEmail."""
    payload = {
        "merchant": "Pago Tarjeta Visa ****3100",
        "amount": 250000,
        "currency": "CLP",
        "transaction_date": "2026-04-05T14:32:00",
        "transaction_type": "transfer",
        "transfer_recipient": "Pago Tarjeta Visa ****3100",
        "card_last_four": "3100",
        "confidence": 0.95,
    }

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=_make_mock_response(payload))

    with patch("modules.email.llm_parser._get_client", return_value=mock_client):
        import modules.email.llm_parser as llm_mod

        llm_mod._circuit_open_until = None
        llm_mod._error_count = 0
        llm_mod._total_count = 0

        from modules.email.llm_parser import parse_with_llm

        result, depth, model_name = await parse_with_llm(
            "Pago a la tarjeta de crédito Visa Signature terminación ****3100 "
            "por un monto de $250.000",
            bank_metadata={"country": "CL", "bank_name": "Banco de Chile"},
        )

    assert result is not None
    assert result.card_last_four == "3100"
    assert result.transaction_type == "transfer"


# ---------------------------------------------------------------------------
# 3 & 4. Ingest-level eager resolution
# ---------------------------------------------------------------------------


async def _seed_household_with_card(
    db, *, card_last_four: str | None
) -> tuple[User, Household, BankAccount | None]:
    user = User(
        id=uuid.uuid4(),
        email=f"card-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="Card Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency="CLP",
    )
    db.add(user)
    await db.flush()

    household = Household(id=uuid.uuid4(), name="Card HH", type="individual")
    db.add(household)
    await db.flush()

    db.add(HouseholdMember(household_id=household.id, user_id=user.id, role="owner"))
    await db.flush()

    account = None
    if card_last_four:
        account = BankAccount(
            id=uuid.uuid4(),
            household_id=household.id,
            user_id=user.id,
            bank_name="Banco de Chile",
            account_type="personal",
            currency="CLP",
            is_active=True,
            account_number=card_last_four,
        )
        db.add(account)
        await db.flush()

    return user, household, account


@pytest.mark.asyncio
async def test_ingest_persists_card_last_four_on_transaction(db):
    """When a BankAccount has account_number matching ParsedEmail.card_last_four,
    the ingest helper must resolve transfer_to_account_id to that account."""
    from modules.email.base import ParsedEmail
    from modules.transactions.models import Transaction
    from jobs.tasks import _resolve_transfer_to_account_id

    user, household, account = await _seed_household_with_card(db, card_last_four="3100")

    parsed = ParsedEmail(
        amount=250000,
        raw_merchant="Pago Tarjeta Visa ****3100",
        transaction_date=datetime.now(timezone.utc),
        bank_name="Banco de Chile",
        transaction_type="transfer",
        currency="CLP",
        card_last_four="3100",
    )

    resolved_id = await _resolve_transfer_to_account_id(db, household.id, parsed.card_last_four)
    assert resolved_id == account.id

    txn = Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=household.id,
        bank_account_id=None,
        raw_merchant_name=parsed.raw_merchant,
        amount=-abs(parsed.amount),
        currency=parsed.currency,
        transaction_date=parsed.transaction_date,
        source="gmail",
        source_bank_name="Banco de Chile",
        status="pending",
        transaction_type="transfer",
        card_last_four=parsed.card_last_four,
        transfer_to_account_id=resolved_id,
    )
    db.add(txn)
    await db.flush()

    assert txn.card_last_four == "3100"
    assert txn.transfer_to_account_id == account.id


@pytest.mark.asyncio
async def test_ingest_leaves_transfer_to_account_id_null_when_no_matching_card(db):
    """When no BankAccount matches card_last_four, transfer_to_account_id must be
    None. card_last_four is still persisted so reconciliation can retry later."""
    from modules.email.base import ParsedEmail
    from modules.transactions.models import Transaction
    from jobs.tasks import _resolve_transfer_to_account_id

    # Seed household with NO matching card
    user, household, _ = await _seed_household_with_card(db, card_last_four=None)

    parsed = ParsedEmail(
        amount=180000,
        raw_merchant="Pago Tarjeta ****9999",
        transaction_date=datetime.now(timezone.utc),
        bank_name="Banco de Chile",
        transaction_type="transfer",
        currency="CLP",
        card_last_four="9999",
    )

    resolved_id = await _resolve_transfer_to_account_id(db, household.id, parsed.card_last_four)
    assert resolved_id is None

    txn = Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=household.id,
        bank_account_id=None,
        raw_merchant_name=parsed.raw_merchant,
        amount=-abs(parsed.amount),
        currency=parsed.currency,
        transaction_date=parsed.transaction_date,
        source="gmail",
        source_bank_name="Banco de Chile",
        status="pending",
        transaction_type="transfer",
        card_last_four=parsed.card_last_four,
        transfer_to_account_id=resolved_id,
    )
    db.add(txn)
    await db.flush()

    assert txn.card_last_four == "9999"
    assert txn.transfer_to_account_id is None
