"""Test the WhatsApp split+category flow without a real purchase.

Creates a fake pending transaction and sends the WhatsApp alert.
You can send multiple to test concurrent message handling.

Usage:
  python3 -m scripts.test_whatsapp_flow                          # one CLP transaction
  python3 -m scripts.test_whatsapp_flow --usd                    # one USD transaction
  python3 -m scripts.test_whatsapp_flow --count 3                # three concurrent messages
  python3 -m scripts.test_whatsapp_flow --merchant "UBER EATS"   # custom merchant
  python3 -m scripts.test_whatsapp_flow --amount 5990            # custom amount (CLP)
  python3 -m scripts.test_whatsapp_flow --usd --amount 1299      # US$12.99 (cents)
"""

import argparse
import asyncio
from datetime import datetime, timezone

import redis.asyncio as aioredis
from sqlalchemy import select

from core.config import settings
from core.database import AsyncSessionLocal
from modules.auth.models import User
from modules.households.models import HouseholdMember
from modules.transactions.models import Transaction
from modules.merchants.service import lookup_merchant
from modules.whatsapp.sender import send_expense_alert
from modules.whatsapp.session import WhatsAppSession, save_session

FAKE_MERCHANTS = [
    "STARBUCKS",
    "UBER EATS",
    "NETFLIX",
    "AMAZON",
    "SPOTIFY",
]


async def send_test_transaction(
    db, redis, user, household_id, merchant: str, amount: int, currency: str
):
    bank_name = "Test Bank" if currency == "USD" else "Banco Test"

    txn = Transaction(
        user_id=user.id,
        household_id=household_id,
        raw_merchant_name=merchant,
        amount=amount,
        currency=currency,
        transaction_date=datetime.now(timezone.utc),
        source="gmail",
        source_bank_name=bank_name,
        status="pending",
    )
    db.add(txn)
    await db.commit()
    await db.refresh(txn)

    phone = user.phone_whatsapp
    categories = await lookup_merchant(merchant, db=db, redis=redis)

    session = WhatsAppSession(
        transaction_id=str(txn.id),
        step="awaiting_split",
        raw_merchant=merchant,
    )
    await save_session(phone, session, redis)

    await send_expense_alert(
        to=phone,
        amount=amount,
        merchant=merchant,
        partner_name="otro miembro",
        is_joint=False,
        categories=categories,
        currency=currency,
        transaction_id=str(txn.id),
    )

    formatted = f"US${amount/100:.2f}" if currency == "USD" else f"${amount:,}"
    print(f"  Sent: {merchant} {formatted} ({currency}) → txn {txn.id}")


async def main():
    parser = argparse.ArgumentParser(description="Test WhatsApp split+category flow")
    parser.add_argument("--count", type=int, default=1, help="Number of test messages to send")
    parser.add_argument("--merchant", type=str, default=None, help="Merchant name")
    parser.add_argument("--amount", type=int, default=None, help="Amount (CLP int or USD cents)")
    parser.add_argument("--usd", action="store_true", help="Use USD instead of CLP")
    parser.add_argument("--email", type=str, default=None, help="User email (default: first user)")
    parser.add_argument(
        "--redis-url",
        type=str,
        default=None,
        help="Redis URL (default: from .env). Use Railway's Redis URL for production testing.",
    )
    args = parser.parse_args()

    currency = "USD" if args.usd else "CLP"
    default_amount = 1599 if args.usd else 15990

    redis_url = args.redis_url or settings.redis_url
    if "localhost" in redis_url:
        print("⚠️  Using localhost Redis. WhatsApp webhooks on Railway use a different Redis.")
        print("   Pass --redis-url <RAILWAY_REDIS_URL> for end-to-end testing.\n")
    redis = await aioredis.from_url(redis_url)

    async with AsyncSessionLocal() as db:
        if args.email:
            result = await db.execute(select(User).where(User.email == args.email))
        else:
            result = await db.execute(select(User).where(User.phone_whatsapp.isnot(None)).limit(1))
        user = result.scalar_one_or_none()
        if not user:
            print("No user found with a verified WhatsApp number.")
            return

        hm_result = await db.execute(
            select(HouseholdMember.household_id).where(HouseholdMember.user_id == user.id)
        )
        household_id = hm_result.scalar_one_or_none()
        if not household_id:
            print(f"User {user.email} has no household.")
            return

        print(f"Sending {args.count} test message(s) to {user.phone_whatsapp} ({user.email}):\n")

        for i in range(args.count):
            merchant = args.merchant or FAKE_MERCHANTS[i % len(FAKE_MERCHANTS)]
            amount = args.amount or (default_amount + i * 1000)
            await send_test_transaction(db, redis, user, household_id, merchant, amount, currency)

    await redis.aclose()
    print("\nDone! Check WhatsApp and reply to test the flow.")


if __name__ == "__main__":
    asyncio.run(main())
