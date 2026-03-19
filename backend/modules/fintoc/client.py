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
            "Authorization": f"Bearer {settings.fintoc_api_key}",
        }

    async def fetch_transactions(
        self, account_id: str, since: date, until: date
    ) -> list[FintocTransaction]:
        all_movements: list[dict] = []
        page = 1
        async with httpx.AsyncClient() as client:
            while True:
                resp = await client.get(
                    f"{FINTOC_BASE}/accounts/{account_id}/movements",
                    headers=self._headers(),
                    params={
                        "link_token": self._link_token,
                        "since": since.isoformat(),
                        "until": until.isoformat(),
                        "per_page": 300,
                        "page": page,
                    },
                )
                if not resp.is_success:
                    raise httpx.HTTPStatusError(
                        f"{resp.status_code} {resp.text}",
                        request=resp.request,
                        response=resp,
                    )
                data = resp.json()
                if not data:
                    break
                all_movements.extend(data)
                if len(data) < 300:
                    break
                page += 1

        return [
            FintocTransaction(
                id=mov["id"],
                amount=abs(int(mov["amount"])),
                description=(mov.get("description") or "").upper().strip(),
                transaction_date=datetime.fromisoformat(mov["post_date"]),
                account_id=account_id,
            )
            for mov in all_movements
            if int(mov.get("amount", 0)) < 0  # only debits (negative = expense)
        ]

    async def fetch_accounts(self) -> list[dict]:
        """Fetch all accounts associated with this link token."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{FINTOC_BASE}/accounts",
                headers=self._headers(),
                params={"link_token": self._link_token},
            )
            if not resp.is_success:
                raise httpx.HTTPStatusError(
                    f"{resp.status_code} {resp.text}",
                    request=resp.request,
                    response=resp,
                )
            return resp.json()
