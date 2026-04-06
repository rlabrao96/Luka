"""Tests for the three-layer parser orchestrator in modules.email.parser."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from modules.email.base import ParsedEmail
from modules.email.parser import parse_bank_email


def _make_parsed_email(**kwargs) -> ParsedEmail:
    defaults = dict(
        amount=15990,
        raw_merchant="LIDER",
        transaction_date=datetime(2026, 3, 10, tzinfo=timezone.utc),
        bank_name="unknown",
        transaction_type="expense",
        currency="CLP",
    )
    defaults.update(kwargs)
    return ParsedEmail(**defaults)


RAW_HTML = "<html>Amount: $15.99 en LIDER</html>"
STRIPPED = "Amount: $15.99 en LIDER"
BANK_META = {"active_template_id": "tmpl-123", "bank_name": "Banco de Chile"}


@pytest.mark.asyncio
async def test_uses_template_when_available():
    """Layer 1: returns template result when template is found and succeeds."""
    template_result = _make_parsed_email()

    with (
        patch(
            "modules.email.parser._get_active_template",
            new=AsyncMock(return_value={"field": "value"}),
        ),
        patch(
            "modules.email.parser.execute_template",
            return_value=template_result,
        ),
    ):
        parsed, parser_used, depth, model = await parse_bank_email(
            RAW_HTML, STRIPPED, bank_metadata=BANK_META
        )

    assert parsed is template_result
    assert parser_used == "template"
    assert depth is None
    assert model is None
    assert parsed.bank_name == "Banco de Chile"


@pytest.mark.asyncio
async def test_falls_through_to_llm_when_no_template():
    """Layer 2: falls through to LLM when no template_id in metadata."""
    llm_result = _make_parsed_email()

    with patch(
        "modules.email.parser.parse_with_llm",
        new=AsyncMock(return_value=(llm_result, 1, "gpt-4o-mini")),
    ):
        parsed, parser_used, depth, model = await parse_bank_email(
            RAW_HTML, STRIPPED, bank_metadata={"bank_name": "BofA"}
        )

    assert parsed is llm_result
    assert parser_used == "llm"
    assert depth == 1
    assert model == "gpt-4o-mini"
    assert parsed.bank_name == "BofA"


@pytest.mark.asyncio
async def test_falls_through_to_regex_when_llm_fails():
    """Layer 3: falls through to regex when LLM returns None."""
    regex_result = _make_parsed_email()

    with (
        patch(
            "modules.email.parser.parse_with_llm",
            new=AsyncMock(return_value=(None, 2, None)),
        ),
        patch(
            "modules.email.parser.parse_bank_email_regex",
            return_value=regex_result,
        ),
    ):
        parsed, parser_used, depth, model = await parse_bank_email(
            RAW_HTML, STRIPPED, bank_metadata=None
        )

    assert parsed is regex_result
    assert parser_used == "regex"
    assert depth is None
    assert model is None


@pytest.mark.asyncio
async def test_template_failure_falls_through_to_llm():
    """Layer 1→2: when execute_template returns None, falls through to LLM."""
    llm_result = _make_parsed_email()

    with (
        patch(
            "modules.email.parser._get_active_template",
            new=AsyncMock(return_value={"field": "value"}),
        ),
        patch(
            "modules.email.parser.execute_template",
            return_value=None,  # template finds nothing
        ),
        patch(
            "modules.email.parser.parse_with_llm",
            new=AsyncMock(return_value=(llm_result, 0, "gpt-4o")),
        ),
    ):
        parsed, parser_used, depth, model = await parse_bank_email(
            RAW_HTML, STRIPPED, bank_metadata=BANK_META
        )

    assert parsed is llm_result
    assert parser_used == "llm"
    assert depth == 0
    assert model == "gpt-4o"
