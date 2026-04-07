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


_EXPENSE_CATEGORIES = [
    "Alimentación",
    "Supermercado",
    "Transporte",
    "Combustible",
    "Entretenimiento",
    "Deporte",
    "Salud",
    "Farmacia",
    "Hogar",
    "Arriendo/Hipoteca",
    "Ropa",
    "Tecnología",
    "Educación",
    "Viajes",
    "Servicios",
    "Cuentas",
    "Inversiones",
    "Otros",
]

_INCOME_CATEGORIES = [
    "Sueldo",
    "Freelance",
    "Inversiones",
    "Arriendo",
    "Bono",
    "Transferencia de terceros",
    "Deuda pendiente",
    "Otros ingresos",
]

_SYSTEM_PROMPT = (
    "Eres un asistente de finanzas personales. "
    "Cuando recibas el nombre de un comercio (de Chile, EE.UU. u otro país), "
    "elige las 3 categorías más apropiadas de esta lista EXACTA de categorías de gastos: "
    f"{', '.join(_EXPENSE_CATEGORIES)}. "
    "No inventes categorías nuevas. Responde ÚNICAMENTE con un JSON. "
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
        model="gemini-2.5-flash-lite",
        contents=f"Comercio: {merchant}",
        config=genai.types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            temperature=0.2,
            max_output_tokens=1024,
            thinking_config=genai.types.ThinkingConfig(thinking_budget=0),
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
