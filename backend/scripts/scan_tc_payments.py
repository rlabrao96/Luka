"""
Scan for Banco de Chile TC payment and transfer emails specifically.
"""

import asyncio
import base64
import sys

sys.path.insert(0, ".")

from core.config import settings
from core.database import AsyncSessionLocal
from core.encryption import decrypt_token
from modules.auth.models import User
from modules.email.parser import parse_bank_email_regex as parse_bank_email, _strip_html
from sqlalchemy import select
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def _extract_body(payload):
    if "body" in payload and payload["body"].get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        result = _extract_body(part)
        if result:
            return result
    return ""


async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        access_token = decrypt_token(user.google_access_token_enc)
        refresh_token = (
            decrypt_token(user.google_refresh_token_enc) if user.google_refresh_token_enc else ""
        )

    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    # Search for all serviciodetransferencias emails
    queries = [
        ("from:serviciodetransferencias@bancochile.cl newer_than:2m", "Transferencias BChile"),
        ('from:enviodigital@bancochile.cl subject:"pago" newer_than:2m', "Pago BChile"),
        ('from:bancochile.cl subject:"Tarjeta de Crédito" newer_than:2m', "TC BChile"),
    ]

    for query, label in queries:
        print(f"\n{'='*80}")
        print(f"{label}: {query}")
        print(f"{'='*80}")

        resp = service.users().messages().list(userId="me", q=query, maxResults=20).execute()
        msgs = resp.get("messages", [])
        print(f"Found: {len(msgs)} emails\n")

        for msg_meta in msgs:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=msg_meta["id"], format="full")
                .execute()
            )

            headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
            subject = headers.get("subject", "")
            from_dt = headers.get("date", "")
            body = _extract_body(msg["payload"])

            # Strip HTML for display
            text = _strip_html(body) if "<html" in body.lower() else body

            parsed = parse_bank_email(body)
            parsed_str = "None"
            if parsed:
                parsed_str = (
                    f"${parsed.amount:,} | {parsed.raw_merchant} | {parsed.transaction_date}"
                )

            print(f"  Subject: {subject}")
            print(f"  Date: {from_dt[:30]}")
            print(f"  Parsed: {parsed_str}")
            print(f"  Text preview: {text[:200]}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
