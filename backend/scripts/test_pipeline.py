"""
Simulate the full transaction pipeline locally against production DB + Redis.
Uses REDIS_URL from .env (set it to Railway Redis URL to test against production).
Run from backend/: python3 scripts/test_pipeline.py
"""

import asyncio
import sys

sys.path.insert(0, ".")

from modules.email.filter import is_financial_email
from modules.email.parser import parse_bank_email_regex as parse_bank_email
from modules.merchants.normalizer import normalize_merchant


TEST_SUBJECT = "Compra con Tarjeta de Crédito"
TEST_SENDER = "Rafael Andrés Labra Oettinger <ralabra@uc.cl>"
TEST_BODY = """Rafael Andres Labra Oettinger:

Te informamos que se ha realizado una compra por $25.990 con Tarjeta de Crédito ****5032 en STARBUCKS PROVIDENCIA SANTIAGO CL el 24/03/2026 15:30.
Revisa Saldos y Movimientos en App Mi Banco o Banco en Línea.

Más información 600 637 3737."""


async def main():
    # Step 1: Pre-filter
    print("=" * 60)
    print("STEP 1: Pre-filter")
    print("=" * 60)
    result = is_financial_email(TEST_SUBJECT, TEST_SENDER, TEST_BODY)
    print(f"  is_financial_email = {result}")
    if not result:
        print("  ❌ BLOCKED by pre-filter.")
        return
    print("  ✅ Passed\n")

    # Step 2: Parser
    print("=" * 60)
    print("STEP 2: Parser")
    print("=" * 60)
    parsed = parse_bank_email(TEST_BODY)
    if not parsed:
        print("  ❌ Parser returned None.")
        from modules.email.parser import _parse_amount, _parse_merchant, _parse_date

        print(f"    Amount: {_parse_amount(TEST_BODY)}")
        print(f"    Merchant: {_parse_merchant(TEST_BODY)}")
        print(f"    Date: {_parse_date(TEST_BODY)}")
        return
    print(f"  Amount: ${parsed.amount:,}")
    print(f"  Merchant: {parsed.raw_merchant}")
    print(f"  Date: {parsed.transaction_date}")
    print("  ✅ Parsed\n")

    # Step 3: Normalization
    print("=" * 60)
    print("STEP 3: Merchant normalization")
    print("=" * 60)
    normalized = normalize_merchant(parsed.raw_merchant)
    print(f"  Raw: {parsed.raw_merchant} → Normalized: {normalized}")
    print("  ✅ Done\n")

    # Step 4: DB checks (household, bank account)
    print("=" * 60)
    print("STEP 4: User + Household + Bank account")
    print("=" * 60)
    from core.database import AsyncSessionLocal
    from modules.auth.models import User
    from modules.households.models import BankAccount, HouseholdMember
    from sqlalchemy import select, and_

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if not user:
            print("  ❌ No user in DB")
            return
        print(f"  User: {user.email}")
        print(f"  WhatsApp: {user.phone_whatsapp}")

        # Bank account (optional)
        bank_result = await db.execute(
            select(BankAccount).where(and_(BankAccount.user_id == user.id, BankAccount.is_active))
        )
        bank_account = bank_result.scalars().first()

        # Household
        household_id = None
        if bank_account:
            household_id = bank_account.household_id
            print(f"  Bank account: {bank_account.bank_name} ({bank_account.account_type})")
        else:
            print("  Bank account: None (email-only mode)")
            hm_result = await db.execute(
                select(HouseholdMember.household_id).where(HouseholdMember.user_id == user.id)
            )
            household_id = hm_result.scalar_one_or_none()

        if not household_id:
            print("  ❌ No household! Pipeline would stop here.")
            return
        print(f"  Household ID: {household_id}")
        print("  ✅ Ready for transaction creation\n")

    # Step 5: Merchant lookup (DB → LLM)
    print("=" * 60)
    print("STEP 5: Merchant lookup (DB → Gemini LLM)")
    print("=" * 60)
    from core.config import settings

    print(f"  GEMINI_API_KEY set: {'Yes' if settings.gemini_api_key else 'NO — will fail!'}")
    print(f"  Redis URL: {settings.redis_url[:30]}...")

    try:
        import redis.asyncio as aioredis
        from modules.merchants.service import lookup_merchant

        redis_client = await aioredis.from_url(settings.redis_url)
        await redis_client.ping()
        print("  Redis: connected ✅")

        async with AsyncSessionLocal() as db:
            categories = await lookup_merchant(parsed.raw_merchant, db=db, redis=redis_client)
            print(f"  Categories: {categories}")
            if categories:
                print("  ✅ Merchant lookup succeeded")
            else:
                print("  ⚠️  Empty categories (LLM may have failed)")
        await redis_client.aclose()
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        import traceback

        traceback.print_exc()
        return

    # Summary
    is_joint = bank_account and bank_account.account_type == "joint"
    print(f"\n{'='*60}")
    print("PIPELINE SUMMARY")
    print(f"{'='*60}")
    print("  Would create transaction:")
    print(f"    Amount: ${parsed.amount:,}")
    print(f"    Merchant: {parsed.raw_merchant}")
    print(f"    Date: {parsed.transaction_date}")
    print(f"    Household: {household_id}")
    print(f"    Bank account: {bank_account.id if bank_account else 'None (email-only)'}")
    print("    Source: gmail")
    print(f"    Categories for WhatsApp: {categories}")
    print(f"    Is joint: {is_joint}")
    print(f"    Next step: {'awaiting_category' if is_joint else 'awaiting_split'}")
    print("\n  ✅ Pipeline would succeed end-to-end!")


if __name__ == "__main__":
    asyncio.run(main())
