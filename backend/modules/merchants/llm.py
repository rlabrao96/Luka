import json
from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential
from core.config import settings

_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


_SYSTEM_PROMPT = (
    "Eres un asistente de finanzas personales chileno. "
    "Cuando recibas el nombre de un comercio de un banco chileno, "
    "responde ÚNICAMENTE con un JSON con exactamente 3 categorías de presupuesto en español. "
    'Formato: {"categories": ["cat1","cat2","cat3"]}'
)


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences that Gemini sometimes wraps around JSON."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return text


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def _call_llm(merchant: str) -> list[str]:
    response = await _get_client().aio.models.generate_content(
        model="gemini-2.0-flash",
        contents=f"Comercio: {merchant}",
        config=genai.types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            temperature=0.2,
            max_output_tokens=100,
        ),
    )
    raw = _strip_code_fences(response.text)
    data = json.loads(raw)
    return data.get("categories", [])[:3]


async def categorize_with_llm(normalized_merchant: str) -> list[str]:
    """
    Ask Gemini for 3 budget categories. Returns [] on failure (caller shows manual selection).
    """
    try:
        return await _call_llm(normalized_merchant)
    except Exception:
        return []
