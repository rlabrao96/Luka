import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Add backend to path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.config import settings
from modules.whatsapp.sender import send_expense_alert, send_category_list
from modules.whatsapp.handler import handle_button_click


async def send_template(to: str, template_name: str = "hello_world"):
    """Send a template message (like the curl example provided by the user)."""
    print(f"\n--- Sending WhatsApp Template: {template_name} ---")
    url = f"https://graph.facebook.com/v19.0/{settings.whatsapp_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {"name": template_name, "language": {"code": "en_US"}},
    }

    import httpx

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload)
        print(f"Status Code: {resp.status_code}")
        print(f"Response: {resp.text}")
        return resp.json()


async def test_sending():
    print("\n--- Testing WhatsApp Sender ---")
    to_phone = "+56912345678"

    # Check if we have real credentials
    has_creds = bool(settings.whatsapp_access_token and settings.whatsapp_phone_number_id)

    if not has_creds:
        print("No WhatsApp credentials found in .env. Mocking the API call...")
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "messaging_product": "whatsapp",
                "contacts": [{"input": to_phone, "wa_id": to_phone}],
                "messages": [{"id": "wamid.HBgLNTY5..."}],
            }
            mock_post.return_value = mock_response

            msg_id = await send_expense_alert(
                to=to_phone,
                amount=15000,
                merchant="Test Merchant",
                partner_name="Cami",
                is_joint=False,
            )

            # Print what was sent
            call_args = mock_post.call_args
            print(f"Mocked Post URL: {call_args.args[0]}")
            print(f"Mocked Post Payload: {call_args.kwargs['json']}")
            print(f"Resulting Message ID: {msg_id}")
    else:
        print("Credentials found! Sending REAL message...")
        try:
            msg_id = await send_expense_alert(
                to=to_phone,
                amount=15000,
                merchant="Test Merchant (Real)",
                partner_name="Partner",
                is_joint=False,
            )
            print(f"Real Message ID: {msg_id}")
        except Exception as e:
            print(f"Error sending real message: {e}")


async def test_handler():
    print("\n--- Testing WhatsApp Handler (Button Click) ---")
    phone = "+56912345678"
    button_id = "split_shared"

    # Mock DB and Redis
    mock_db = AsyncMock()
    mock_redis = AsyncMock()

    # Mock get_session to return a valid session
    mock_session = MagicMock()
    mock_session.transaction_id = "txn_123"
    mock_session.raw_merchant = "Lider"

    with patch("modules.whatsapp.handler.get_session", return_value=mock_session):
        with patch("modules.whatsapp.handler.save_session") as mock_save:
            with patch(
                "modules.whatsapp.handler.lookup_merchant", return_value=["Alimentos", "Hogar"]
            ):
                with patch(
                    "modules.whatsapp.handler.send_category_list", return_value="wamid.list_123"
                ) as mock_send_list:
                    await handle_button_click(phone, button_id, mock_db, mock_redis)

                    print(f"Handled button click: {button_id}")
                    print(
                        f"Session updated: step={mock_session.step}, split_type={mock_session.split_type}"
                    )
                    mock_save.assert_called_once()
                    mock_send_list.assert_called_once()
                    print("Handler logic verified successfully (Mocked).")


if __name__ == "__main__":
    to_phone = "17373950861"

    # 2. Test Poll (interactive)
    print(f"\n--- Sending WhatsApp Category List (Poll) to {to_phone} ---")
    amount = 25000
    merchant = "Lider"
    categories = ["Alimentos", "Hogar", "Otros"]
    msg_id = asyncio.run(
        send_category_list(
            to=to_phone,
            categories=categories,
            context_msg=f"Vimos un cargo de ${amount:,} en {merchant}. ¿En qué lo gastaste?",
        )
    )
    print(f"Message Sent! ID: {msg_id}")

    # Optional: Run the other tests
    # asyncio.run(send_template(to="+17373950861", template_name="hello_world"))
    # asyncio.run(test_sending())
    # asyncio.run(test_handler())
