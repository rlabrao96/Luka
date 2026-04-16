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


# --- Currency formatting ---

# (symbol, decimals, thousands_sep, decimal_sep)
_CURRENCY_FMT: dict[str, tuple[str, int, str, str]] = {
    "CLP": ("CLP$", 0, ".", ""),
    "COP": ("COP$", 0, ".", ""),
    "PYG": ("₲",   0, ".", ""),
    "CRC": ("₡",   0, ".", ""),
    "USD": ("US$",  2, ",", "."),
    "MXN": ("MX$",  2, ",", "."),
    "PEN": ("S/",   2, ",", "."),
    "BOB": ("Bs.",  2, ",", "."),
    "DOP": ("RD$",  2, ",", "."),
    "GTQ": ("Q",    2, ",", "."),
    "HNL": ("L",    2, ",", "."),
    "NIO": ("C$",   2, ",", "."),
    "BRL": ("R$",   2, ".", ","),
    "ARS": ("AR$",  2, ".", ","),
    "UYU": ("$U",   2, ".", ","),
    "VES": ("Bs.S", 2, ".", ","),
}


def _format_amount(amount: float, currency: str = "CLP") -> str:
    """Format transaction amount for WhatsApp display using per-currency rules."""
    amount = abs(amount)
    fmt = _CURRENCY_FMT.get(currency)
    if fmt is None:
        # Unknown currency — plain integer with currency code prefix
        return f"{currency} {int(amount):,}"

    symbol, decimals, thou_sep, dec_sep = fmt

    if decimals == 0:
        # Integer formatting with thousands separator
        n = int(round(amount))
        formatted = f"{n:,}".replace(",", thou_sep)
        return f"{symbol}{formatted}"
    else:
        # Two-decimal formatting
        integer_part = int(amount)
        frac = round((amount - integer_part) * 100)
        int_str = f"{integer_part:,}".replace(",", thou_sep)
        return f"{symbol}{int_str}{dec_sep}{frac:02d}"


async def send_expense_alert(
    to: str,
    amount: int,
    merchant: str,
    partner_name: str,
    is_joint: bool,
    categories: list[str] | None = None,
    transaction_type: str = "expense",
    currency: str = "CLP",
) -> str:
    """Send expense alert with split buttons (personal/shared/edit). Returns message ID."""
    formatted = _format_amount(amount, currency)

    if is_joint:
        body_text = f"_¡Luka registró un nuevo gasto!_\n*Comercio:* {merchant}\n*Monto:* {formatted}\n¿Qué categoría le asignamos?"
        return await send_category_list(to=to, categories=categories or [], context_msg=body_text)

    body_text = f"_¡Luka registró un nuevo gasto!_\n*Comercio:* {merchant}\n*Monto:* {formatted}\n¿De qué bolsa es?"
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
                    {"type": "reply", "reply": {"id": "split_personal", "title": "Personal"}},
                    {"type": "reply", "reply": {"id": "split_shared", "title": "Compartido"}},
                    {
                        "type": "reply",
                        "reply": {"id": "transaction_error", "title": "Editar Transacción"},
                    },
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


async def send_category_list(to: str, categories: list[str], context_msg: str | None = None) -> str:
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


async def send_transfer_alert(to: str, amount: int, merchant: str, currency: str = "CLP") -> str:
    """Send informational transfer alert (no split buttons). Returns message ID."""
    formatted = _format_amount(amount, currency)
    body = f"_Luka registró una transferencia_\n*Destino:* {merchant}\n*Monto:* {formatted}"
    return await send_text(to, body)


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


async def send_edit_options(to: str) -> str:
    """Send a 2-button message for editing merchant name or amount. Returns message ID."""
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": "¿Qué deseas editar?"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "edit_merchant", "title": "Comercio"}},
                    {"type": "reply", "reply": {"id": "edit_amount", "title": "Monto"}},
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
