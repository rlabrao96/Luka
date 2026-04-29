"""Repair orphan transfer/refund pair_ids.

A pair_id is "orphan" when only one row in the database carries it — its
partner has been deleted, leaving the surviving row stuck with a pair_id no
twin holds. Stuck rows are skipped by ``detect_transfers`` / ``detect_refunds``
and never re-pair.

This script finds every orphan ``transfer_pair_id`` and ``refund_pair_id``
(globally, or scoped to one household) and nulls them out. Idempotent: a
second run is a no-op.

Usage:
    python -m scripts.repair_orphan_pair_ids --dry-run
    python -m scripts.repair_orphan_pair_ids
    python -m scripts.repair_orphan_pair_ids --household-id <UUID>
    python -m scripts.repair_orphan_pair_ids --rerun-detect
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid

from sqlalchemy import func, select, update as sql_update

from core.database import AsyncSessionLocal

# Register every ORM model so Base.metadata can resolve cross-table FKs
# before any flush.
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
import modules.transactions.models  # noqa: F401
from modules.reconciliation.transfers import detect_transfers
from modules.transactions.models import Transaction


async def _orphan_pair_ids(db, column, household_id: uuid.UUID | None) -> list[uuid.UUID]:
    """Return pair_ids that exactly one row carries (optionally scoped to one household)."""
    stmt = select(column).where(column.is_not(None)).group_by(column).having(func.count() == 1)
    if household_id is not None:
        stmt = stmt.where(Transaction.household_id == household_id)
    return list((await db.execute(stmt)).scalars().all())


async def main(dry_run: bool, household_id: uuid.UUID | None, rerun_detect: bool) -> int:
    async with AsyncSessionLocal() as db:
        scope = f"household={household_id}" if household_id else "all households"
        print(f"[repair] scope: {scope} dry_run={dry_run} rerun_detect={rerun_detect}")

        orphan_transfers = await _orphan_pair_ids(db, Transaction.transfer_pair_id, household_id)
        orphan_refunds = await _orphan_pair_ids(db, Transaction.refund_pair_id, household_id)

        print(
            f"[repair] {len(orphan_transfers)} orphan transfer pair_ids, "
            f"{len(orphan_refunds)} orphan refund pair_ids"
        )

        for column, ids in (
            (Transaction.transfer_pair_id, orphan_transfers),
            (Transaction.refund_pair_id, orphan_refunds),
        ):
            if not ids:
                continue
            stmt = sql_update(Transaction).where(column.in_(ids)).values({column: None})
            if household_id is not None:
                stmt = stmt.where(Transaction.household_id == household_id)
            await db.execute(stmt)

        if rerun_detect:
            # Rerun detect_transfers per household so freshly-unstuck rows are eligible.
            if household_id is not None:
                target_households = [household_id]
            else:
                target_households = list(
                    (await db.execute(select(Transaction.household_id).distinct())).scalars().all()
                )
            for hid in target_households:
                pairs = await detect_transfers(db, hid)
                print(f"  [repair] household {hid}: detect_transfers paired {pairs}")

        if dry_run:
            await db.rollback()
            print("[repair] dry-run — rolled back.")
        else:
            await db.commit()
            print("[repair] committed.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--household-id", type=uuid.UUID, default=None)
    parser.add_argument(
        "--rerun-detect",
        action="store_true",
        help="After clearing orphans, run detect_transfers per affected household.",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.dry_run, args.household_id, args.rerun_detect)))
