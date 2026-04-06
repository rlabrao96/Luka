"""One-off script: fix BofA transactions created before USD parsing was added.

Run: python3 -m scripts.fix_bofa_transactions
"""

import asyncio
from core.database import AsyncSessionLocal
from modules.email.parser import parse_bank_email_regex as parse_bank_email
from sqlalchemy import text


async def main():
    async with AsyncSessionLocal() as db:
        # Find email transactions with BofA-like amounts (< $100 stored as CLP integers)
        result = await db.execute(
            text("""
                SELECT id, raw_merchant_name, amount, currency, raw_email_text
                FROM transactions
                WHERE source IN ('gmail', 'outlook')
                  AND raw_email_text IS NOT NULL
                  AND currency = 'CLP'
                  AND amount IN (784, 1196, 2396, 1708)
            """)
        )
        rows = result.all()

        if not rows:
            print("No BofA transactions found to fix.")
            return

        print(f"Found {len(rows)} transactions to fix:\n")

        for row in rows:
            txn_id, old_merchant, old_amount, old_currency, raw_email = row

            parsed = parse_bank_email(raw_email)
            if parsed and parsed.currency == "USD":
                await db.execute(
                    text("""
                        UPDATE transactions
                        SET raw_merchant_name = :merchant,
                            amount = :amount,
                            currency = 'USD',
                            source_bank_name = 'Bank of America'
                        WHERE id = :id
                    """),
                    {
                        "id": txn_id,
                        "merchant": parsed.raw_merchant,
                        "amount": parsed.amount,
                    },
                )
                print(
                    f"  FIXED: {old_merchant} ${old_amount:,.0f} {old_currency}"
                    f" → {parsed.raw_merchant} {parsed.amount} cents USD"
                )
            else:
                print(f"  SKIPPED (re-parse didn't detect USD): {old_merchant} ${old_amount:,.0f}")

        await db.commit()
        print("\nDone! Transactions updated.")


if __name__ == "__main__":
    asyncio.run(main())
