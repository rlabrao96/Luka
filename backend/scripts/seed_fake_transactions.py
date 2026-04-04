"""
Send 3 fake WhatsApp expense alerts for buenahorarojas@gmail.com.

Looks up the user + their household + phone, creates 3 Transaction rows,
builds a WhatsApp session in Redis for each one, and fires the real
send_expense_alert() call so the messages land on the phone.

Usage (from /backend):
    python scripts/seed_fake_transactions.py
"""
import asyncio
import sys
import os
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from core.database import AsyncSessionLocal
import redis.asyncio as aioredis
from core.config import settings
from modules.auth.models import User
from modules.households.models import HouseholdMember, BankAccount
from modules.transactions.models import Transaction
from modules.merchants.models import Merchant  # noqa: F401 — registers table in metadata
from modules.merchants.service import lookup_merchant
from modules.whatsapp.sender import send_expense_alert
from modules.whatsapp.session import WhatsAppSession, save_session, save_msgid

TARGET_EMAIL = "buenahorarojas@gmail.com"

FAKE_TRANSACTIONS = [
    {"merchant": "Lider", "amount": 23_490, "category_hint": "Alimentos"},
    {"merchant": "Starbucks", "amount": 5_200, "category_hint": "Restaurantes"},
    {"merchant": "Copec", "amount": 48_000, "category_hint": "Transporte"},
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        # 1. Fetch user
        result = await db.execute(select(User).where(User.email == TARGET_EMAIL))
        user = result.scalar_one_or_none()
        if not user:
            print(f"User '{TARGET_EMAIL}' not found in DB.")
            return
        print(f"Found user: {user.full_name} ({user.email})")

        if not user.phone_whatsapp:
            print("User has no phone_whatsapp set — cannot send WhatsApp messages.")
            return
        print(f"WhatsApp phone: {user.phone_whatsapp}")

        # 2. Fetch household membership
        member_result = await db.execute(
            select(HouseholdMember).where(HouseholdMember.user_id == user.id)
        )
        member = member_result.scalar_one_or_none()
        if not member:
            print("User has no household membership.")
            return
        household_id = member.household_id
        print(f"Household ID: {household_id}")

        # 3. Try to find a bank account to attach (optional, can be None)
        bank_result = await db.execute(
            select(BankAccount).where(
                BankAccount.user_id == user.id,
                BankAccount.is_active == True,
            )
        )
        bank_account = bank_result.scalars().first()
        bank_account_id = bank_account.id if bank_account else None
        is_joint = bank_account.account_type == "joint" if bank_account else False
        print(f"Bank account: {bank_account.bank_name if bank_account else 'none'} (joint={is_joint})")

        # 4. Open Redis
        redis_client = await aioredis.from_url(settings.redis_url, decode_responses=True)

        # 5. Create transactions + send alerts
        for i, fake in enumerate(FAKE_TRANSACTIONS, start=1):
            txn = Transaction(
                user_id=user.id,
                household_id=household_id,
                bank_account_id=bank_account_id,
                raw_merchant_name=fake["merchant"],
                amount=fake["amount"],
                currency="CLP",
                transaction_date=datetime.now(timezone.utc),
                source="manual",
                source_type="manual",
                status="settled",
                transaction_type="expense",
            )
            db.add(txn)
            await db.commit()
            await db.refresh(txn)
            print(f"\n[{i}/3] Created transaction {txn.id} — {fake['merchant']} ${fake['amount']:,}")

            # Build WhatsApp session
            session = WhatsAppSession(
                transaction_id=str(txn.id),
                step="awaiting_category" if is_joint else "awaiting_split",
                raw_merchant=fake["merchant"],
            )
            await save_session(user.phone_whatsapp, session, redis_client)

            # Look up suggested categories for this merchant
            categories = await lookup_merchant(fake["merchant"], db=db, redis=redis_client)

            # Send the WhatsApp alert
            msg_id = await send_expense_alert(
                to=user.phone_whatsapp,
                amount=fake["amount"],
                merchant=fake["merchant"],
                partner_name="tu pareja",
                is_joint=is_joint,
                categories=categories,
            )
            await save_msgid(msg_id, str(txn.id), redis_client)
            print(f"    WhatsApp message sent — ID: {msg_id}")

        await redis_client.aclose()
        print("\nDone. 3 fake transactions created and WhatsApp alerts sent.")


if __name__ == "__main__":
    asyncio.run(main())
