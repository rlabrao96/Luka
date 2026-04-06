"""Tests for the LLM email parser with confidence waterfall."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Unit tests — pure functions (no async, no mocks needed)
# ---------------------------------------------------------------------------


def test_waterfall_models_ordered():
    """WATERFALL_MODELS must be ordered cheapest to most expensive (thresholds descending)."""
    from modules.email.llm_parser import WATERFALL_MODELS

    thresholds = [m["threshold"] for m in WATERFALL_MODELS]
    assert thresholds == sorted(
        thresholds, reverse=True
    ), "WATERFALL_MODELS thresholds must be descending (cheapest model has highest threshold)"
    assert len(WATERFALL_MODELS) == 4


def test_build_system_prompt_cl_currency():
    """System prompt for CL country must include CLP currency rule."""
    from modules.email.llm_parser import _build_system_prompt

    prompt = _build_system_prompt({"country": "CL", "bank_name": "Banco BCI"})
    assert "CLP" in prompt
    assert "pesos" in prompt.lower()
    assert "Banco BCI" in prompt


def test_build_system_prompt_br_context():
    """System prompt for BR country must include bank name and BRL rule."""
    from modules.email.llm_parser import _build_system_prompt

    prompt = _build_system_prompt({"country": "BR", "bank_name": "Nubank"})
    assert "BRL" in prompt
    assert "centavos" in prompt.lower()
    assert "Nubank" in prompt
    assert "(BR)" in prompt


def test_parse_llm_response_valid_json():
    """_parse_llm_response returns a dict for valid JSON with all required fields."""
    from modules.email.llm_parser import _parse_llm_response

    raw = """{
        "merchant": "LIDER",
        "amount": 15990,
        "currency": "CLP",
        "transaction_date": "2026-04-05T14:32:00",
        "transaction_type": "expense",
        "confidence": 0.95
    }"""
    result = _parse_llm_response(raw)
    assert result is not None
    assert result["merchant"] == "LIDER"
    assert result["amount"] == 15990
    assert result["confidence"] == 0.95


def test_parse_llm_response_strips_code_fences():
    """_parse_llm_response handles JSON wrapped in markdown code fences."""
    from modules.email.llm_parser import _parse_llm_response

    raw = '```json\n{"merchant":"COPEC","amount":5000,"currency":"CLP","transaction_date":"2026-04-05T10:00:00","transaction_type":"expense","confidence":0.9}\n```'
    result = _parse_llm_response(raw)
    assert result is not None
    assert result["merchant"] == "COPEC"


def test_parse_llm_response_missing_required_fields():
    """_parse_llm_response returns None when required fields are absent."""
    from modules.email.llm_parser import _parse_llm_response

    # Missing 'confidence'
    raw = '{"merchant":"LIDER","amount":15990,"currency":"CLP","transaction_date":"2026-04-05T14:32:00","transaction_type":"expense"}'
    assert _parse_llm_response(raw) is None


def test_parse_llm_response_malformed_json():
    """_parse_llm_response returns None for malformed / non-JSON text."""
    from modules.email.llm_parser import _parse_llm_response

    assert _parse_llm_response("not json at all") is None
    assert _parse_llm_response("{broken: json}") is None
    assert _parse_llm_response("") is None


# ---------------------------------------------------------------------------
# Async tests — mock Gemini client
# ---------------------------------------------------------------------------


def _make_mock_response(data: dict) -> MagicMock:
    import json

    mock = MagicMock()
    mock.text = json.dumps(data)
    return mock


@pytest.mark.asyncio
async def test_parse_with_llm_success():
    """parse_with_llm returns a ParsedEmail on a high-confidence first-model response."""
    payload = {
        "merchant": "LIDER",
        "amount": 15990,
        "currency": "CLP",
        "transaction_date": "2026-04-05T14:32:00",
        "transaction_type": "expense",
        "transfer_recipient": None,
        "card_last_four": "4532",
        "confidence": 0.95,
    }

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=_make_mock_response(payload))

    with patch("modules.email.llm_parser._get_client", return_value=mock_client):
        # Reset module-level circuit breaker state
        import modules.email.llm_parser as llm_mod

        llm_mod._circuit_open_until = None
        llm_mod._error_count = 0
        llm_mod._total_count = 0

        from modules.email.llm_parser import parse_with_llm

        result, depth, model_name = await parse_with_llm(
            "Su compra en LIDER por $15.990 fue procesada.",
            bank_metadata={"country": "CL", "bank_name": "BCI"},
        )

    assert result is not None
    assert result.raw_merchant == "LIDER"
    assert result.amount == 15990
    assert result.currency == "CLP"
    assert result.card_last_four == "4532"
    assert result.confidence == 0.95
    assert depth == 1
    assert model_name == "gemini-3.1-flash-lite"


@pytest.mark.asyncio
async def test_parse_with_llm_escalates_on_low_confidence():
    """parse_with_llm escalates to the next model when confidence is below threshold."""
    import json

    low_confidence_payload = {
        "merchant": "UNKNOWN",
        "amount": 5000,
        "currency": "CLP",
        "transaction_date": "2026-04-05T10:00:00",
        "transaction_type": "expense",
        "transfer_recipient": None,
        "card_last_four": None,
        "confidence": 0.5,  # below 0.9 threshold for first model
    }
    high_confidence_payload = {
        "merchant": "WALMART",
        "amount": 32000,
        "currency": "CLP",
        "transaction_date": "2026-04-05T10:00:00",
        "transaction_type": "expense",
        "transfer_recipient": None,
        "card_last_four": "1234",
        "confidence": 0.85,  # above 0.8 threshold for second model
    }

    low_mock = MagicMock()
    low_mock.text = json.dumps(low_confidence_payload)
    high_mock = MagicMock()
    high_mock.text = json.dumps(high_confidence_payload)

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=[low_mock, high_mock])

    with patch("modules.email.llm_parser._get_client", return_value=mock_client):
        import modules.email.llm_parser as llm_mod

        llm_mod._circuit_open_until = None
        llm_mod._error_count = 0
        llm_mod._total_count = 0

        from modules.email.llm_parser import parse_with_llm

        result, depth, model_name = await parse_with_llm(
            "Compra en tienda por $32.000",
            bank_metadata={"country": "CL", "bank_name": "Santander"},
        )

    assert result is not None
    assert result.raw_merchant == "WALMART"
    assert result.confidence == 0.85
    assert depth == 2  # second model in waterfall
    assert model_name == "gemini-2.5-flash"


@pytest.mark.asyncio
async def test_parse_with_llm_returns_none_on_total_failure():
    """parse_with_llm returns (None, 4, None) when all models raise exceptions."""
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=Exception("API error"))

    with patch("modules.email.llm_parser._get_client", return_value=mock_client):
        import modules.email.llm_parser as llm_mod

        llm_mod._circuit_open_until = None
        llm_mod._error_count = 0
        llm_mod._total_count = 0

        from modules.email.llm_parser import parse_with_llm, WATERFALL_MODELS

        result, depth, model_name = await parse_with_llm(
            "Mensaje de banco ilegible",
            bank_metadata=None,
        )

    assert result is None
    assert depth == len(WATERFALL_MODELS)
    assert model_name is None
