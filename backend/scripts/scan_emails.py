"""
One-off script: Scan last 2 months of Gmail and test the email pre-filter.
Run from backend/: python3 scripts/scan_emails.py
"""

import asyncio
import base64
import sys
from datetime import datetime, timezone

# Ensure backend modules are importable
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


async def main():
    # 1. Get user from DB
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if not user:
            print("No user found in database.")
            return

        print(f"User: {user.email}")

        if not user.google_access_token_enc:
            print("No Google tokens stored for this user.")
            return

        access_token = decrypt_token(user.google_access_token_enc)
        refresh_token = (
            decrypt_token(user.google_refresh_token_enc) if user.google_refresh_token_enc else ""
        )

    # 2. Build Gmail service
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    # 3. Fetch messages from last 2 months
    print("\nFetching emails from last 2 months...\n")
    messages = []
    page_token = None

    while True:
        resp = (
            service.users()
            .messages()
            .list(
                userId="me",
                q="newer_than:2m",
                maxResults=100,
                pageToken=page_token,
            )
            .execute()
        )
        messages.extend(resp.get("messages", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    print(f"Total emails found: {len(messages)}\n")

    # 4. Process each message through the filter
    financial_emails = []
    non_financial_count = 0

    for i, msg_meta in enumerate(messages):
        msg = (
            service.users().messages().get(userId="me", id=msg_meta["id"], format="full").execute()
        )

        # Extract headers
        headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
        subject = headers.get("subject", "(no subject)")
        sender = headers.get("from", "")
        received_at = datetime.fromtimestamp(
            int(msg.get("internalDate", 0)) / 1000, tz=timezone.utc
        )

        # Extract body
        body = _extract_body(msg["payload"])

        # Run pre-filter
        is_financial = is_financial_email(subject, sender, body)

        if is_financial:
            # Also try the parser
            parsed = parse_bank_email(body)
            financial_emails.append(
                {
                    "date": received_at.strftime("%Y-%m-%d %H:%M"),
                    "from": sender[:50],
                    "subject": subject[:60],
                    "parsed": parsed,
                }
            )
        else:
            non_financial_count += 1

        # Progress
        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(messages)} emails...")

    # 5. Print results
    print(f"\n{'='*80}")
    print(f"RESULTS: {len(financial_emails)} financial / {non_financial_count} non-financial")
    print(f"{'='*80}\n")

    print("FINANCIAL EMAILS (matched pre-filter):\n")
    for email in financial_emails:
        parsed_str = ""
        if email["parsed"]:
            p = email["parsed"]
            parsed_str = (
                f" → ${p.amount:,} at {p.raw_merchant} ({p.transaction_date.strftime('%Y-%m-%d')})"
            )
        else:
            parsed_str = " → [filter: YES, parser: no match]"

        print(f"  {email['date']}  {email['from']}")
        print(f"    Subject: {email['subject']}")
        print(f"    {parsed_str}")
        print()


def _extract_body(payload: dict) -> str:
    """Extract text body from Gmail message payload."""
    # Simple text/plain or text/html
    if "body" in payload and payload["body"].get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    # Multipart
    parts = payload.get("parts", [])
    for part in parts:
        mime = part.get("mimeType", "")
        if mime == "text/plain" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
        if mime == "text/html" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
        # Nested multipart
        if part.get("parts"):
            result = _extract_body(part)
            if result:
                return result

    return ""


if __name__ == "__main__":
    asyncio.run(main())
