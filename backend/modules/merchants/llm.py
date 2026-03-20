import json
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from core.config import settings

openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

_SYSTEM_PROMPT = (
    "Eres un asistente de finanzas personales chileno. "
    "Cuando recibas el nombre de un comercio de un banco chileno, "
    "responde ÚNICAMENTE con un JSON con exactamente 4 categorías de presupuesto en español. "
    'Formato: {"categories": ["cat1","cat2","cat3","cat4"]}'
)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def _call_llm(merchant: str) -> list[str]:
    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Comercio: {merchant}"},
        ],
        temperature=0.2,
        max_tokens=100,
        timeout=30,
    )
    raw = response.choices[0].message.content
    data = json.loads(raw)
    return data.get("categories", [])[:4]


async def categorize_with_llm(normalized_merchant: str) -> list[str]:
    """
    Ask LLM for 4 budget categories. Returns [] on failure (caller shows manual selection).
    """
    try:
        return await _call_llm(normalized_merchant)
    except Exception:
        return []
