"""
Scan last 2 months of Gmail and show only successfully parsed bank transactions.
Run from backend/: python3 scripts/scan_transactions.py
"""

import asyncio
import base64
import sys

sys.path.insert(0, ".")

from core.config import settings
from core.database import AsyncSessionLocal
from core.encryption import decrypt_token
from modules.auth.models import User
from modules.email.filter import is_financial_email
from modules.email.parser import parse_bank_email_regex as parse_bank_email
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

    print("Fetching emails from last 2 months...")
    messages = []
    page_token = None
    while True:
        resp = (
            service.users()
            .messages()
            .list(userId="me", q="newer_than:2m", maxResults=100, pageToken=page_token)
            .execute()
        )
        messages.extend(resp.get("messages", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    print(f"Total emails: {len(messages)}\n")

    transactions = []

    for i, msg_meta in enumerate(messages):
        msg = (
            service.users().messages().get(userId="me", id=msg_meta["id"], format="full").execute()
        )

        headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
        subject = headers.get("subject", "")
        sender = headers.get("from", "")
        body = _extract_body(msg["payload"])

        if not is_financial_email(subject, sender, body):
            continue

        parsed = parse_bank_email(body)
        if not parsed:
            continue

        # Sanity check: skip if merchant looks like HTML garbage or boilerplate
        bad_merchants = {
            "AND",
            "BLUE CONTENT",
            "FORMA EXITOSA",
            "FORMA EXITOSA CON",
            "LA BARRA DEL NAVEGADOR",
            "TABLES IN OUTLOOK 2007 AND UP",
            "A ROLE THEY",
            "FOR WHEN YOU",
            "WAITING FOR IT",
            "SOUTH AFRICA AND THE SEYCHELLES",
            "BOOKED THROUGH DELTA",
            "WOMENS SUMMER OUTFITS SPONSORED",
            "WOMEN",
            "SANS",
            "PERLECARE MATTRESS TOPPER",
            "LÍNEA",
            "SALUDAR",
            "COMUNICARNOS CONTIGO DE INMEDIATO SI ELEG",
            "ESTAR SUJETO A MODIFICACIONES SEGÚN CONVE",
        }
        if parsed.raw_merchant in bad_merchants:
            continue

        # Skip if amount seems unreasonable for a single transaction (> 10M CLP)
        if parsed.amount > 10_000_000:
            continue

        # Determine bank from sender
        bank = "Unknown"
        sender_lower = sender.lower()
        if "bancochile" in sender_lower:
            bank = "Banco de Chile"
        elif "santander" in sender_lower:
            bank = "Santander"
        elif "bci" in sender_lower:
            bank = "BCI"
        elif "falabella" in sender_lower:
            bank = "Banco Falabella"
        elif "bankofamerica" in sender_lower or "bofa" in sender_lower:
            bank = "Bank of America"
        elif "scotiabank" in sender_lower:
            bank = "Scotiabank"

        transactions.append(
            {
                "date": parsed.transaction_date.strftime("%Y-%m-%d"),
                "amount": parsed.amount,
                "merchant": parsed.raw_merchant[:35],
                "bank": bank,
                "sender": sender[:40],
            }
        )

        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(messages)}...")

    # Sort by date descending
    transactions.sort(key=lambda t: t["date"], reverse=True)

    # Print table
    print(f"\n{'='*90}")
    print(f"PARSED TRANSACTIONS: {len(transactions)} found")
    print(f"{'='*90}")
    print(f"{'Date':<12} {'Amount':>12} {'Merchant':<35} {'Bank':<20}")
    print(f"{'-'*12} {'-'*12} {'-'*35} {'-'*20}")

    total = 0
    for t in transactions:
        amount_str = f"${t['amount']:,.0f}"
        print(f"{t['date']:<12} {amount_str:>12} {t['merchant']:<35} {t['bank']:<20}")
        total += t["amount"]

    print(f"{'-'*12} {'-'*12} {'-'*35} {'-'*20}")
    print(f"{'TOTAL':<12} {f'${total:,.0f}':>12}")


if __name__ == "__main__":
    asyncio.run(main())
