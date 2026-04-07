"""LLM-powered email parser with confidence-based model waterfall."""

import json
import logging
from datetime import datetime, timedelta

import google.genai as genai

from core.config import settings
from modules.email.base import ParsedEmail

logger = logging.getLogger(__name__)

_client = None

# Circuit breaker state
_error_count = 0
_total_count = 0
_circuit_open_until: datetime | None = None
_CIRCUIT_BREAKER_THRESHOLD = 0.5
_CIRCUIT_BREAKER_WINDOW = 20
_CIRCUIT_BREAKER_COOLDOWN = 900  # 15 min

WATERFALL_MODELS = [
    {"name": "gemini-2.5-flash-lite", "threshold": 0.9},
    {"name": "gemini-2.5-flash", "threshold": 0.8},
    {"name": "gemini-2.0-flash", "threshold": 0.7},
    {"name": "gemini-2.5-pro", "threshold": 0.0},
]

_REQUIRED_FIELDS = {
    "merchant",
    "amount",
    "currency",
    "transaction_date",
    "transaction_type",
    "confidence",
}


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
- merchant: exact merchant/store name from the email, cleaned of location suffixes.
  For person-to-person transfers, use the RECIPIENT PERSON NAME (e.g. "Camila Chahuan"), NOT the bank name.
  For credit card payments ("pago a tarjeta", "Comprobante Pago Tarjeta"), use "Pago Tarjeta" + card info (e.g. "Pago Tarjeta Visa ****5032").
- amount: integer in the smallest currency unit as specified above
- transaction_type: "expense" for purchases, "transfer" for inter-account moves AND credit card payments, "income" for deposits/inflows
- transfer_recipient: the person/entity name when transaction_type is "transfer" (same as merchant).
  For CC payments, use the card description (e.g. "Pago Tarjeta Visa ****5032").
- confidence: 0.0 to 1.0 — how certain you are about the extraction accuracy
- If you cannot extract a required field, set confidence below 0.3
"""


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def _parse_llm_response(raw_text: str) -> dict | None:
    try:
        cleaned = _strip_code_fences(raw_text)
        data = json.loads(cleaned)
        if not _REQUIRED_FIELDS.issubset(data.keys()):
            return None
        return data
    except (json.JSONDecodeError, TypeError):
        return None


def _extraction_to_parsed_email(data: dict) -> ParsedEmail:
    tx_date = data["transaction_date"]
    if isinstance(tx_date, str):
        tx_date = datetime.fromisoformat(tx_date)

    # For transfers, prefer recipient name over generic bank name as merchant
    merchant = data["merchant"]
    if data.get("transaction_type") == "transfer" and data.get("transfer_recipient"):
        merchant = data["transfer_recipient"]

    return ParsedEmail(
        amount=int(data["amount"]),
        raw_merchant=merchant,
        transaction_date=tx_date,
        bank_name="",
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
    global _error_count, _total_count, _circuit_open_until

    # Circuit breaker check
    if _circuit_open_until and datetime.utcnow() < _circuit_open_until:
        logger.warning("Circuit breaker open — skipping LLM")
        return None, 0, None

    thresholds = [float(t) for t in settings.llm_waterfall_thresholds.split(",")]
    system_prompt = _build_system_prompt(bank_metadata)
    client = _get_client()
    api_failed = False

    for i, model_cfg in enumerate(WATERFALL_MODELS):
        model_name = model_cfg["name"]
        threshold = thresholds[i] if i < len(thresholds) else model_cfg["threshold"]

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
                raw_text = response.text if response.text else None
                if not raw_text:
                    logger.warning("Empty LLM response from %s, escalating", model_name)
                    break
                data = _parse_llm_response(raw_text)
                if data is None:
                    logger.warning("Malformed LLM response from %s, escalating", model_name)
                    break

                if data["confidence"] >= threshold:
                    parsed = _extraction_to_parsed_email(data)
                    return parsed, i + 1, model_name

                logger.info(
                    "Low confidence %.2f from %s (threshold %.2f), escalating",
                    data["confidence"],
                    model_name,
                    threshold,
                )
                break

            except Exception as e:
                if attempt == 0:
                    logger.warning("API error from %s (attempt 1): %s, retrying", model_name, e)
                    continue
                logger.warning("API error from %s (attempt 2): %s, escalating", model_name, e)
                api_failed = True
                break

    # Update circuit breaker
    _total_count += 1
    if api_failed:
        _error_count += 1
    if _total_count >= _CIRCUIT_BREAKER_WINDOW:
        error_rate = _error_count / _total_count
        if error_rate >= _CIRCUIT_BREAKER_THRESHOLD:
            _circuit_open_until = datetime.utcnow() + timedelta(seconds=_CIRCUIT_BREAKER_COOLDOWN)
            logger.error("Circuit breaker OPEN — %.0f%% error rate", error_rate * 100)
        _error_count = 0
        _total_count = 0

    return None, len(WATERFALL_MODELS), None
