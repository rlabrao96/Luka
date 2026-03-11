import base64
from datetime import datetime, timezone
from modules.email.base import EmailProvider, RawEmail


class GmailProvider(EmailProvider):
    def __init__(self, access_token: str, refresh_token: str):
        self._access_token = access_token
        self._refresh_token = refresh_token

    def _build_service(self):
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials

        creds = Credentials(
            token=self._access_token,
            refresh_token=self._refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
        )
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    async def setup_watch(self, user_id: str) -> dict:
        from core.config import settings

        service = self._build_service()
        result = (
            service.users()
            .watch(
                userId="me",
                body={
                    "topicName": f"projects/{settings.gcp_project_id}/topics/luka-gmail",
                    "labelIds": ["INBOX"],
                },
            )
            .execute()
        )
        return {"subscription_id": result.get("historyId"), "expiry": result.get("expiration")}

    async def fetch_new_emails(self, user_id: str, history_id: str = None) -> list[RawEmail]:
        service = self._build_service()
        if not history_id:
            return []
        history = (
            service.users()
            .history()
            .list(userId="me", startHistoryId=history_id, historyTypes=["messageAdded"])
            .execute()
        )
        emails = []
        for record in history.get("history", []):
            for msg_ref in record.get("messagesAdded", []):
                msg = (
                    service.users()
                    .messages()
                    .get(userId="me", id=msg_ref["message"]["id"], format="full")
                    .execute()
                )
                emails.append(self._parse_gmail_message(msg))
        return emails

    def _parse_gmail_message(self, msg: dict) -> RawEmail:
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        body = ""
        if "data" in msg["payload"].get("body", {}):
            body = base64.urlsafe_b64decode(msg["payload"]["body"]["data"]).decode(
                "utf-8", errors="ignore"
            )
        return RawEmail(
            message_id=msg["id"],
            subject=headers.get("Subject", ""),
            sender=headers.get("From", ""),
            body=body,
            received_at=datetime.now(timezone.utc),
        )

    async def renew_watch(self, user_id: str) -> None:
        await self.setup_watch(user_id)
