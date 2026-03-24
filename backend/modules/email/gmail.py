import asyncio
import base64
from datetime import datetime, timezone

from modules.email.base import EmailProvider, RawEmail


class GmailProvider(EmailProvider):
    def __init__(self, access_token: str, refresh_token: str):
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._creds = None

    def _build_service(self):
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        from core.config import settings

        self._creds = Credentials(
            token=self._access_token,
            refresh_token=self._refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
        )
        return build("gmail", "v1", credentials=self._creds, cache_discovery=False)

    def get_current_token(self) -> str | None:
        """Return the current access token (may have been refreshed by the SDK)."""
        return self._creds.token if self._creds else None

    async def setup_watch(self, user_id: str) -> dict:
        from core.config import settings

        service = self._build_service()
        body = {
            "topicName": f"projects/{settings.gcp_project_id}/topics/{settings.gmail_pubsub_topic}",
            "labelIds": ["INBOX"],
        }
        result = await asyncio.to_thread(service.users().watch(userId="me", body=body).execute)
        return {
            "subscription_id": result.get("historyId"),
            "expiry": result.get("expiration"),
        }

    async def fetch_new_emails(
        self, user_id: str, history_id: str = None, **kwargs
    ) -> list[RawEmail]:
        service = self._build_service()
        if not history_id:
            return []

        emails = []
        seen_ids = set()

        # Try History API first
        try:
            history = await asyncio.to_thread(
                service.users()
                .history()
                .list(userId="me", startHistoryId=history_id, historyTypes=["messageAdded"])
                .execute
            )
            for record in history.get("history", []):
                for msg_ref in record.get("messagesAdded", []):
                    msg_id = msg_ref["message"]["id"]
                    if msg_id in seen_ids:
                        continue
                    seen_ids.add(msg_id)
                    msg = await asyncio.to_thread(
                        service.users()
                        .messages()
                        .get(userId="me", id=msg_id, format="full")
                        .execute
                    )
                    emails.append(self._parse_gmail_message(msg))
        except Exception as e:
            print(f"[GMAIL] History API failed: {e}", flush=True)

        # Fallback: if History API returned nothing, fetch latest INBOX message
        if not emails:
            try:
                result = await asyncio.to_thread(
                    service.users()
                    .messages()
                    .list(userId="me", labelIds=["INBOX"], maxResults=1)
                    .execute
                )
                for msg_ref in result.get("messages", []):
                    msg = await asyncio.to_thread(
                        service.users()
                        .messages()
                        .get(userId="me", id=msg_ref["id"], format="full")
                        .execute
                    )
                    emails.append(self._parse_gmail_message(msg))
            except Exception as e:
                print(f"[GMAIL] Fallback fetch failed: {e}", flush=True)

        return emails

    def _parse_gmail_message(self, msg: dict) -> RawEmail:
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        body = ""
        if "data" in msg["payload"].get("body", {}):
            body = base64.urlsafe_b64decode(msg["payload"]["body"]["data"]).decode(
                "utf-8", errors="ignore"
            )
        # Use Gmail's internalDate (ms since epoch) for accurate received time
        internal_date_ms = msg.get("internalDate")
        if internal_date_ms:
            received_at = datetime.fromtimestamp(int(internal_date_ms) / 1000, tz=timezone.utc)
        else:
            received_at = datetime.now(timezone.utc)

        return RawEmail(
            message_id=msg["id"],
            subject=headers.get("Subject", ""),
            sender=headers.get("From", ""),
            body=body,
            received_at=received_at,
        )

    async def renew_watch(self, user_id: str) -> dict:
        """Renew watch — returns same dict as setup_watch (subscription_id, expiry)."""
        return await self.setup_watch(user_id)
