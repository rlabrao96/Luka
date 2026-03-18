import pytest
import uuid
from unittest.mock import AsyncMock, patch

HOUSEHOLD_ID = str(uuid.uuid4())


@pytest.mark.asyncio
async def test_get_fintoc_accounts_returns_list(http_client, override_auth, override_db):
    mock_accounts = [
        {
            "id": "acc_1",
            "name": "Cuenta Corriente",
            "type": "checking_account",
            "number": "****1234",
        },
    ]
    with patch("modules.bank_accounts.router.FintocClient") as MockClient:
        instance = AsyncMock()
        instance.fetch_accounts = AsyncMock(return_value=mock_accounts)
        MockClient.return_value = instance

        response = await http_client.get("/bank-accounts/fintoc/accounts?link_token=lt_test")

    assert response.status_code == 200
    assert response.json() == mock_accounts


@pytest.mark.asyncio
async def test_get_fintoc_accounts_requires_auth(http_client):
    response = await http_client.get("/bank-accounts/fintoc/accounts?link_token=lt_test")
    assert response.status_code in (401, 403)  # unauthenticated
