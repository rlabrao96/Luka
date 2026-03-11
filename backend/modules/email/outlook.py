import httpx
from datetime import datetime, timezone
from modules.email.base import EmailProvider, RawEmail

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class OutlookProvider(EmailProvider):
    def __init__(self, access_token: str):
        self._token = access_token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    async def setup_watch(self, user_id: str) -> dict:
        from core.config import settings

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{GRAPH_BASE}/subscriptions",
                headers=self._headers(),
                json={
                    "changeType": "created",
                    "notificationUrl": f"{settings.frontend_url.replace('3000', '8000')}/webhooks/outlook",
                    "resource": "me/messages",
                    "expirationDateTime": "2026-03-13T18:00:00Z",
                    "clientState": settings.outlook_client_state,
                },
            )
            data = resp.json()
            return {"subscription_id": data.get("id"), "expiry": data.get("expirationDateTime")}

    async def fetch_new_emails(self, user_id: str, message_id: str = None) -> list[RawEmail]:
        if not message_id:
            return []
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GRAPH_BASE}/me/messages/{message_id}",
                headers=self._headers(),
                params={"$select": "id,subject,from,body,receivedDateTime"},
            )
            msg = resp.json()
            return [
                RawEmail(
                    message_id=msg["id"],
                    subject=msg.get("subject", ""),
                    sender=msg.get("from", {}).get("emailAddress", {}).get("address", ""),
                    body=msg.get("body", {}).get("content", ""),
                    received_at=datetime.fromisoformat(
                        msg.get("receivedDateTime", "").rstrip("Z")
                    ).replace(tzinfo=timezone.utc),
                )
            ]

    async def renew_watch(self, user_id: str) -> None:
        pass  # PATCH subscription expiry — implemented in production
