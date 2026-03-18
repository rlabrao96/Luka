from dataclasses import dataclass
from datetime import datetime, date
import httpx
from core.config import settings

FINTOC_BASE = "https://api.fintoc.com/v1"


@dataclass
class FintocTransaction:
    id: str
    amount: int
    description: str
    transaction_date: datetime
    account_id: str


class FintocClient:
    def __init__(self, link_token: str):
        self._link_token = link_token

    def _headers(self) -> dict:
        return {
            "Authorization": settings.fintoc_api_key,
            "X-Link-Token": self._link_token,
        }

    async def fetch_transactions(
        self, account_id: str, since: date, until: date
    ) -> list[FintocTransaction]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{FINTOC_BASE}/accounts/{account_id}/transactions",
                headers=self._headers(),
                params={"since": since.isoformat(), "until": until.isoformat()},
            )
            resp.raise_for_status()
            data = resp.json()

        return [
            FintocTransaction(
                id=txn["id"],
                amount=abs(int(txn["amount"])),
                description=(txn.get("description") or "").upper().strip(),
                transaction_date=datetime.fromisoformat(txn["post_date"]),
                account_id=account_id,
            )
            for txn in data
            if txn.get("type") == "charge"  # only debits
        ]

    async def fetch_accounts(self) -> list[dict]:
        """Fetch all accounts associated with this link token."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.fintoc.com/v1/accounts",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()
