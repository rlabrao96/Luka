"""
Debug: Strip HTML and show the text content the parser actually sees.
"""

import asyncio
import base64
import re
import sys

sys.path.insert(0, ".")

from core.config import settings
from core.database import AsyncSessionLocal
from core.encryption import decrypt_token
from modules.auth.models import User
from modules.email.parser import parse_bank_email_regex as parse_bank_email
from sqlalchemy import select
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def strip_html(html: str) -> str:
    """Strip HTML tags and collapse whitespace to see what regex sees."""
    text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&[a-z]+;", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


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
            print(f"\nSubject: {headers.get('subject', '')}")

            # Get raw HTML body
            html_body = _extract_html(msg["payload"])
            if not html_body:
                print("  [no HTML body]")
                continue

            # Show stripped text (what parser actually tries to match)
            text = strip_html(html_body)
            print("\nSTRIPPED TEXT (first 1500 chars):")
            print(text[:1500])

            # Show what the current parser extracts
            parsed = parse_bank_email(html_body)
            print("\nPARSER RESULT (on raw HTML):")
            if parsed:
                print(f"  Amount: ${parsed.amount:,}")
                print(f"  Merchant: {parsed.raw_merchant}")
                print(f"  Date: {parsed.transaction_date}")
            else:
                print("  None (no match)")

            # Also try parser on stripped text
            parsed2 = parse_bank_email(text)
            print("\nPARSER RESULT (on stripped text):")
            if parsed2:
                print(f"  Amount: ${parsed2.amount:,}")
                print(f"  Merchant: {parsed2.raw_merchant}")
                print(f"  Date: {parsed2.transaction_date}")
            else:
                print("  None (no match)")


def _extract_html(payload):
    if payload.get("mimeType") == "text/html" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        result = _extract_html(part)
        if result:
            return result
    return None


if __name__ == "__main__":
    asyncio.run(main())
