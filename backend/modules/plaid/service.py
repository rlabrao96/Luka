import uuid

import plaid
from plaid.api import plaid_api
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.item_remove_request import ItemRemoveRequest

from core.config import settings

# Singleton client — reuses HTTP connection pool across calls
_client: plaid_api.PlaidApi | None = None


def _get_client() -> plaid_api.PlaidApi:
    global _client
    if _client is None:
        env_map = {
            "sandbox": plaid.Environment.Sandbox,
            "production": plaid.Environment.Production,
        }
        configuration = plaid.Configuration(
            host=env_map.get(settings.plaid_env, plaid.Environment.Sandbox),
            api_key={
                "clientId": settings.plaid_client_id,
                "secret": settings.plaid_secret,
            },
        )
        api_client = plaid.ApiClient(configuration)
        _client = plaid_api.PlaidApi(api_client)
    return _client


def create_link_token(user_id: uuid.UUID) -> str:
    client = _get_client()
    request = LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id=str(user_id)),
        client_name="Luka",
        products=[Products("transactions")],
        country_codes=[CountryCode("US")],
        language="en",
    )
    response = client.link_token_create(request)
    return response.link_token


def exchange_public_token(public_token: str) -> tuple[str, str]:
    client = _get_client()
    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    response = client.item_public_token_exchange(request)
    return response.access_token, response.item_id


def sync_transactions(access_token: str, cursor: str | None, count: int = 500):
    client = _get_client()
    request = TransactionsSyncRequest(
        access_token=access_token,
        count=count,
    )
    if cursor:
        request.cursor = cursor
    response = client.transactions_sync(request)
    return response


def remove_item(access_token: str) -> None:
    client = _get_client()
    request = ItemRemoveRequest(access_token=access_token)
    client.item_remove(request)
