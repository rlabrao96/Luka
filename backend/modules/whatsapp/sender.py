import httpx
from core.config import settings

_API_BASE = "https://graph.facebook.com/v22.0"
_TIMEOUT = httpx.Timeout(15.0)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json",
    }


def _url() -> str:
    return f"{_API_BASE}/{settings.whatsapp_phone_number_id}/messages"


async def send_expense_alert(
    to: str,
    amount: int,
    merchant: str,
    partner_name: str,
    is_joint: bool,
    categories: list[str] | None = None,
) -> str:
    """Send expense alert with split buttons (personal/partner/shared). Returns message ID."""
    if is_joint:
        # Joint account: skip split question, go straight to category
        body_text = f"Gasto compartido de ${amount:,} en {merchant}. ¿Qué categoría le asignamos?"
        return await send_category_list(to=to, categories=categories or [], context_msg=body_text)

    body_text = f"Gasto de ${amount:,} en {merchant}. ¿Cómo lo dividimos?"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body_text},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "split_personal", "title": "Mío"}},
                    {
                        "type": "reply",
                        "reply": {"id": "split_partner", "title": f"De {partner_name}"},
                    },
                    {"type": "reply", "reply": {"id": "split_shared", "title": "Compartido"}},
                ]
            },
        },
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(_url(), headers=_headers(), json=payload)
        data = resp.json()
        if resp.status_code != 200:
            raise Exception(f"WhatsApp API Error: {data}")
    return data["messages"][0]["id"]


async def send_category_list(to: str, categories: list[str], context_msg: str = None) -> str:
    """Send list message with category options. Returns WhatsApp message ID."""
    rows = [{"id": f"cat_{i}", "title": cat} for i, cat in enumerate(categories)]
    body_text = context_msg or "¿A qué categoría pertenece este gasto?"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body_text},
            "action": {
                "button": "Ver categorías",
                "sections": [{"title": "Categorías", "rows": rows}],
            },
        },
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(_url(), headers=_headers(), json=payload)
        data = resp.json()
        if resp.status_code != 200:
            raise Exception(f"WhatsApp API Error: {data}")
    return data["messages"][0]["id"]


async def send_text(to: str, body: str) -> str:
    """Send a simple text message. Returns message ID."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(_url(), headers=_headers(), json=payload)
        data = resp.json()
        if resp.status_code != 200:
            raise Exception(f"WhatsApp API Error: {data}")
    return data["messages"][0]["id"]


async def send_verification_pin(to: str, pin: str) -> None:
    """Send a text message with a verification PIN. Raises on failure."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {
            "body": (
                f"\U0001f510 Tu código de verificación Luka es: {pin}\n\n"
                "No compartas este código con nadie. Expira en 5 minutos."
            )
        },
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(_url(), headers=_headers(), json=payload)
        if resp.status_code != 200:
            data = resp.json()
            raise Exception(f"WhatsApp API Error: {data}")
