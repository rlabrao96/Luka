"""Diagnostic: inspect the Apple / Uber Eats rows that aren't refund-pairing
for Rafael. Prints the fields detect_refunds buckets on so we can see why."""

import asyncio

from sqlalchemy import text

import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
import modules.transactions.models  # noqa: F401
from core.database import AsyncSessionLocal

RAFAEL_USER_ID = "b1ffd32f-094a-4258-a688-ac2116606ebd"


async def main() -> None:
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            text(
                """
                SELECT id, raw_merchant_name, merchant_id, bank_account_id,
                       amount, currency, transaction_date::date,
                       transfer_pair_id, refund_pair_id, source_type, status
                FROM transactions
                WHERE user_id = :uid
                  AND (raw_merchant_name ILIKE '%apple%'
                       OR raw_merchant_name ILIKE '%uber%')
                  AND transaction_date >= now() - interval '10 days'
                ORDER BY transaction_date DESC
                """
            ),
            {"uid": RAFAEL_USER_ID},
        )
        cols = [
            "id",
            "raw_merchant_name",
            "merchant_id",
            "bank_account_id",
            "amount",
            "currency",
            "date",
            "transfer_pair_id",
            "refund_pair_id",
            "source_type",
            "status",
        ]
        print("\t".join(cols))
        for row in res:
            print("\t".join(str(v) for v in row))


if __name__ == "__main__":
    asyncio.run(main())
