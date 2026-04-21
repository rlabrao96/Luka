"""One-time cleanup for Rafael's pending-transaction backlog.

Runs the reconciliation tick against every household Rafael belongs to:
rematches aging email pendings, detects transfer/refund pairs, and promotes
the remainder to 'orphan'. Idempotent — safe to re-run.

Usage:
    python -m scripts.cleanup_rafael_pending --dry-run   # no commit
    python -m scripts.cleanup_rafael_pending             # commits

Override the target email with --email if running for another account.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from core.database import AsyncSessionLocal

# Register every ORM model so Base.metadata can resolve cross-table FKs
# (Transaction.merchant_id -> merchants.id, etc.) before any flush.
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
import modules.transactions.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import HouseholdMember
from modules.reconciliation.tick import reconciliation_tick_for_household

DEFAULT_EMAIL = "rafaellabra96@gmail.com"


async def main(email: str, dry_run: bool) -> int:
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            print(f"[cleanup] no user found for {email}", file=sys.stderr)
            return 1

        household_ids = (
            (
                await db.execute(
                    select(HouseholdMember.household_id).where(HouseholdMember.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )

        print(f"[cleanup] user={user.id} email={email} households={len(household_ids)}")
        grand_totals = {"rematched": 0, "transfers": 0, "refunds": 0, "orphaned": 0}
        for hid in household_ids:
            result = await reconciliation_tick_for_household(db, hid)
            for k in grand_totals:
                grand_totals[k] += result[k]
            print(f"  household {hid}: {result}")

        if dry_run:
            await db.rollback()
            print(f"[cleanup] dry-run — rolled back. Totals: {grand_totals}")
        else:
            await db.commit()
            print(f"[cleanup] committed. Totals: {grand_totals}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.email, args.dry_run)))
