import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_send_personal_expense_alert_calls_meta_api():
    with patch("modules.whatsapp.sender.httpx.AsyncClient") as mock_http:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"messages": [{"id": "wamid.123"}]}
        mock_response.status_code = 200
        mock_ctx.post = AsyncMock(return_value=mock_response)
        mock_http.return_value = mock_ctx

        from modules.whatsapp.sender import send_expense_alert

        result = await send_expense_alert(
            to="+56912345678",
            amount=15990,
            merchant="Lider",
            partner_name="Cami",
            is_joint=False,
        )
    assert result == "wamid.123"


@pytest.mark.asyncio
async def test_send_category_list_calls_meta_api():
    with patch("modules.whatsapp.sender.httpx.AsyncClient") as mock_http:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"messages": [{"id": "wamid.456"}]}
        mock_response.status_code = 200
        mock_ctx.post = AsyncMock(return_value=mock_response)
        mock_http.return_value = mock_ctx

        from modules.whatsapp.sender import send_category_list

        result = await send_category_list(
            to="+56912345678",
            categories=["Supermercado", "Retail", "Alimentos", "Hogar"],
        )
    assert result == "wamid.456"
