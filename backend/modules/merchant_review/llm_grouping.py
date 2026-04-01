import json
import logging

from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential

from modules.merchants.llm import _get_client, _strip_code_fences

logger = logging.getLogger(__name__)

_GROUPING_PROMPT = """You are a banking data specialist. Given a list of raw merchant names from bank statements, group them by BUSINESS ENTITY.

Rules:
- Group ONLY when the same company/brand (different branches OK)
- NEVER group by business type (two different restaurants = separate)
- NEVER group different services from same company (e.g., Uber Trips ≠ Uber Eats)
- NEVER group different businesses that share a category (e.g., "Estacionamiento PR" ≠ "Estacionamiento Vita")
- When in doubt, keep separate
- Generate a clean display name for each group
- Fix casing (ALL CAPS → proper case)
- Remove bank transaction prefixes (COMPRA, PAGO, CARGO, PURCHASE, etc.)
- Keep the business name recognizable

Respond ONLY with JSON. Format:
[
  {"display_name": "Clean Name", "raw_names": ["RAW1", "RAW2"]},
  ...
]"""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def _call_grouping_llm(raw_names: list[str]) -> list[dict]:
    response = await _get_client().aio.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=f"Raw merchant names:\n{json.dumps(raw_names)}",
        config=genai.types.GenerateContentConfig(
            system_instruction=_GROUPING_PROMPT,
            temperature=0.2,
            max_output_tokens=4096,
            thinking_config=genai.types.ThinkingConfig(thinking_budget=0),
        ),
    )
    raw = _strip_code_fences(response.text)
    return json.loads(raw)


def _fallback_grouping(raw_names: list[str]) -> list[dict]:
    """If LLM fails, each name becomes its own group with title-cased name."""
    result = []
    for name in raw_names:
        # Strip common prefixes for display
        display = name
        for prefix in ("COMPRA ", "PAGO ", "CARGO ", "PURCHASE "):
            if display.upper().startswith(prefix):
                display = display[len(prefix) :]
                break
        result.append(
            {
                "display_name": display.strip().title(),
                "raw_names": [name],
            }
        )
    return result


async def group_raw_merchants(raw_names: list[str]) -> list[dict]:
    """
    Group raw merchant names into canonical merchant proposals.
    Returns: [{"display_name": "Lider", "raw_names": ["LIDER PROVIDENCIA", ...]}, ...]
    """
    if not raw_names:
        return []

    try:
        return await _call_grouping_llm(raw_names)
    except Exception:
        logger.exception("LLM grouping failed, falling back to individual grouping")
        return _fallback_grouping(raw_names)
