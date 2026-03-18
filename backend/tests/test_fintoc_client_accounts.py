import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from modules.fintoc.client import FintocClient


@pytest.mark.asyncio
async def test_fetch_accounts_returns_account_list():
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            "id": "acc_123",
            "name": "Cuenta Corriente",
            "type": "checking_account",
            "number": "****1234",
        },
        {
            "id": "acc_456",
            "name": "Tarjeta de Crédito",
            "type": "credit_card",
            "number": "****5678",
        },
    ]
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as MockHttpx:
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.get = AsyncMock(return_value=mock_response)
        MockHttpx.return_value = mock_http

        client = FintocClient(link_token="lt_test")
        accounts = await client.fetch_accounts()

    assert len(accounts) == 2
    assert accounts[0]["id"] == "acc_123"
    assert accounts[1]["type"] == "credit_card"
