"""
Debug script: Fetch raw Banco de Chile emails and print their exact bodies.
Run from backend/: python3 scripts/debug_email_body.py
"""

import asyncio
import base64
import sys

sys.path.insert(0, ".")

from core.config import settings
from core.database import AsyncSessionLocal
from core.encryption import decrypt_token
from modules.auth.models import User
from sqlalchemy import select
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def _extract_body_parts(payload, parts_out):
    """Recursively extract all text body parts."""
    if "body" in payload and payload["body"].get("data"):
        mime = payload.get("mimeType", "unknown")
        decoded = base64.urlsafe_b64decode(payload["body"]["data"]).decode(
            "utf-8", errors="replace"
        )
        parts_out.append((mime, decoded))

    for part in payload.get("parts", []):
        _extract_body_parts(part, parts_out)


async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if not user or not user.google_access_token_enc:
            print("No user/tokens found.")
            return

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

    queries = [
        ('from:"enviodigital@bancochile.cl" subject:"Compra con Tarjeta"', 2),
        ('from:"serviciodetransferencias@bancochile.cl" subject:"Transferencia"', 1),
        ('from:"serviciodetransferencias@bancochile.cl" subject:"Comprobante"', 1),
    ]

    for query, count in queries:
        print(f"\n{'='*80}")
        print(f"QUERY: {query}")
        print(f"{'='*80}")

        resp = service.users().messages().list(userId="me", q=query, maxResults=count).execute()
        for msg_meta in resp.get("messages", []):
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=msg_meta["id"], format="full")
                .execute()
            )

            headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
            print(f"\nFrom: {headers.get('from', '')}")
            print(f"Subject: {headers.get('subject', '')}")

            parts = []
            _extract_body_parts(msg["payload"], parts)

            for mime, body in parts:
                print(f"\n--- [{mime}] ---")
                # Print first 2000 chars
                print(body[:2000])
                if len(body) > 2000:
                    print(f"\n... ({len(body)} total chars)")


if __name__ == "__main__":
    asyncio.run(main())
