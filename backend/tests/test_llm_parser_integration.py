"""Integration tests for the three-layer parser pipeline.

Tests the interaction between parse_bank_email (orchestrator),
parse_with_llm (LLM layer), and parse_bank_email_regex (regex fallback).
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from modules.email.parser import parse_bank_email, parse_bank_email_regex
from modules.email.base import ParsedEmail

# Real Banco de Chile transaction email sample
BANCO_CHILE_EMAIL = (
    "Te informamos que se ha realizado una compra por $15.990 con Tarjeta de Credito ****5032 "
    "en LIDER EXPRESS SANTIAGO CL el 05/04/2026 14:32."
)

BANCO_CHILE_METADATA = {
    "active_template_id": None,
    "bank_name": "Banco de Chile",
    "country": "CL",
}


# ---------------------------------------------------------------------------
# Test 1: Full pipeline — LLM path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_pipeline_llm_path():
    """Full pipeline: no template → LLM parses successfully → returns ParsedEmail with correct bank_name."""
    llm_result = ParsedEmail(
        amount=15990,
        raw_merchant="LIDER EXPRESS",
        transaction_date=datetime(2026, 4, 5, 14, 32),
        bank_name="",
        transaction_type="expense",
        currency="CLP",
        card_last_four="5032",
        confidence=0.96,
    )

    with patch(
        "modules.email.parser.parse_with_llm",
        new=AsyncMock(return_value=(llm_result, 1, "gemini-3.1-flash-lite")),
    ):
        parsed, parser_used, depth, model = await parse_bank_email(
            raw_html=BANCO_CHILE_EMAIL,
            stripped_text=BANCO_CHILE_EMAIL,
            bank_metadata=BANCO_CHILE_METADATA,
        )

    assert parsed is not None
    assert isinstance(parsed, ParsedEmail)
    assert parsed.bank_name == "Banco de Chile"
    assert parsed.amount == 15990
    assert parsed.currency == "CLP"
    assert parser_used == "llm"
    assert depth == 1
    assert model == "gemini-3.1-flash-lite"


# ---------------------------------------------------------------------------
# Test 2: Full pipeline — regex fallback when LLM returns None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_pipeline_regex_fallback():
    """Full pipeline: LLM returns None → falls back to regex → still returns a ParsedEmail."""
    with patch(
        "modules.email.parser.parse_with_llm",
        new=AsyncMock(return_value=(None, 4, None)),
    ):
        parsed, parser_used, depth, model = await parse_bank_email(
            raw_html=BANCO_CHILE_EMAIL,
            stripped_text=BANCO_CHILE_EMAIL,
            bank_metadata=BANCO_CHILE_METADATA,
        )

    assert parsed is not None
    assert isinstance(parsed, ParsedEmail)
    # Regex layer extracts the core fields
    assert parsed.amount == 15990
    assert parsed.currency == "CLP"
    assert "LIDER" in parsed.raw_merchant
    assert parser_used == "regex"
    assert depth is None
    assert model is None


# ---------------------------------------------------------------------------
# Test 3: Regex parser standalone
# ---------------------------------------------------------------------------


def test_regex_parser_standalone_banco_chile():
    """parse_bank_email_regex correctly parses the Banco de Chile sample without any mocking."""
    result = parse_bank_email_regex(BANCO_CHILE_EMAIL)

    assert result is not None
    assert isinstance(result, ParsedEmail)
    assert result.amount == 15990
    assert result.currency == "CLP"
    assert "LIDER" in result.raw_merchant
    # Date extracted from the email text
    assert result.transaction_date.day == 5
    assert result.transaction_date.month == 4
    assert result.transaction_date.year == 2026
