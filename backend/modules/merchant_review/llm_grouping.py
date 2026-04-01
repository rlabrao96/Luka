import json
import logging
import re

from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential

from modules.merchants.llm import _get_client, _strip_code_fences

logger = logging.getLogger(__name__)

_BATCH_SIZE = 50  # Max names per LLM call to avoid malformed JSON

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

Respond ONLY with valid JSON array. No trailing commas. Format:
[
  {"display_name": "Clean Name", "raw_names": ["RAW1", "RAW2"]}
]"""


def _fix_json(raw: str) -> str:
    """Fix common LLM JSON issues: trailing commas before ] or }."""
    raw = re.sub(r",\s*]", "]", raw)
    raw = re.sub(r",\s*}", "}", raw)
    return raw


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def _call_grouping_llm(raw_names: list[str]) -> list[dict]:
    response = await _get_client().aio.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=f"Raw merchant names:\n{json.dumps(raw_names)}",
        config=genai.types.GenerateContentConfig(
            system_instruction=_GROUPING_PROMPT,
            temperature=0.2,
            max_output_tokens=8192,
            thinking_config=genai.types.ThinkingConfig(thinking_budget=0),
        ),
    )
    raw = _strip_code_fences(response.text)
    raw = _fix_json(raw)
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
    Batches into chunks of _BATCH_SIZE to avoid LLM output limits.
    Returns: [{"display_name": "Lider", "raw_names": ["LIDER PROVIDENCIA", ...]}, ...]
    """
    if not raw_names:
        return []

    all_groups = []
    for i in range(0, len(raw_names), _BATCH_SIZE):
        batch = raw_names[i : i + _BATCH_SIZE]
        batch_num = i // _BATCH_SIZE + 1
        total_batches = (len(raw_names) + _BATCH_SIZE - 1) // _BATCH_SIZE
        logger.info("Processing batch %d/%d (%d names)", batch_num, total_batches, len(batch))

        try:
            groups = await _call_grouping_llm(batch)
            all_groups.extend(groups)
        except Exception:
            logger.exception(
                "LLM grouping failed for batch %d, falling back for this batch", batch_num
            )
            all_groups.extend(_fallback_grouping(batch))

    return all_groups
