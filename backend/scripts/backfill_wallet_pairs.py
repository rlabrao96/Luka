"""One-time backfill: detect wallet funding pairs across a household's full history.

Dry-run by default — prints a table of candidate pairs, then rolls back.
Pass --apply to commit.

Usage:
    python -m scripts.backfill_wallet_pairs --email rafaellabra96@gmail.com
    python -m scripts.backfill_wallet_pairs --email rafaellabra96@gmail.com --apply
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid

from sqlalchemy import select

from core.database import AsyncSessionLocal

# Register ORM models for metadata resolution.
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
import modules.transactions.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, HouseholdMember
from modules.reconciliation.wallets import detect_wallet_pairs
from modules.transactions.models import Transaction

# 10 years covers all possible history; effectively "no cap".
_FULL_HISTORY_DAYS = 365 * 10


async def _snapshot_paired_ids(db, household_id: uuid.UUID) -> set[uuid.UUID]:
    """IDs of transactions already paired before the run."""
    ids = (
        (
            await db.execute(
                select(Transaction.id).where(
                    Transaction.household_id == household_id,
                    Transaction.transfer_pair_id.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    return set(ids)


async def _print_new_pairs(db, household_id: uuid.UUID, pre_ids: set[uuid.UUID]) -> None:
    """Print a table of pairs created by this run (not present in pre_ids)."""
    stmt = (
        select(Transaction, BankAccount)
        .join(BankAccount, Transaction.bank_account_id == BankAccount.id)
        .where(
            Transaction.household_id == household_id,
            Transaction.transfer_pair_id.is_not(None),
        )
        .order_by(Transaction.transfer_pair_id, Transaction.transaction_date)
    )
    if pre_ids:
        stmt = stmt.where(Transaction.id.not_in(pre_ids))
    rows = (await db.execute(stmt)).all()

    by_pair: dict[uuid.UUID, list] = {}
    for tx, acct in rows:
        by_pair.setdefault(tx.transfer_pair_id, []).append((tx, acct))

    if not by_pair:
        return

    header = f"{'pair':>4} | {'date':>10} | {'amount':>10} | {'account':<24} | merchant"
    print(header)
    print("-" * len(header))
    for i, (_pid, legs) in enumerate(by_pair.items(), start=1):
        for tx, acct in legs:
            print(
                f"{i:>4} | {tx.transaction_date.date().isoformat():>10} | "
                f"{float(tx.amount):>10.2f} | {(acct.bank_name or '')[:24]:<24} | "
                f"{tx.raw_merchant_name or ''}"
            )


async def main(email: str, apply_changes: bool) -> int:
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            print(f"No user with email {email}", file=sys.stderr)
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

        if not household_ids:
            print(f"User {email} has no households", file=sys.stderr)
            return 1

        total_pairs = 0
        for hid in household_ids:
            pre_ids = await _snapshot_paired_ids(db, hid)
            pairs = await detect_wallet_pairs(db, hid, lookback_days=_FULL_HISTORY_DAYS)
            print(f"\nHousehold {hid}: {pairs} wallet pair(s) detected")
            if pairs:
                await _print_new_pairs(db, hid, pre_ids)
            total_pairs += pairs

        if apply_changes:
            await db.commit()
            print(f"\nCOMMITTED {total_pairs} pair(s).")
        else:
            await db.rollback()
            print(f"\nDRY RUN — {total_pairs} pair(s) would be created. " "Re-run with --apply.")

        return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--email", default="rafaellabra96@gmail.com")
    ap.add_argument("--apply", action="store_true", help="Commit changes (default: dry-run)")
    args = ap.parse_args()
    sys.exit(asyncio.run(main(args.email, args.apply)))
