"""Refund/reversal detection: identifies same-account refund pairs.

A refund pair is two transactions on the SAME `bank_account_id` with the same
currency, the same normalized `raw_merchant_name`, equal absolute amount,
opposite signs, and the refund dated 0–90 days after the charge.

When detected, both rows get a shared `refund_pair_id`. `transaction_type` is
NOT changed — the charge stays `expense`, the refund stays `income`. Consumers
(budget math, analytics) are expected to skip rows with a non-null
`refund_pair_id` when they want net-of-refund numbers.
"""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from modules.transactions.models import Transaction


def _normalize_merchant(name: str | None) -> str:
    """Lowercase + collapse whitespace. Matches the detector's grouping key."""
    return " ".join((name or "").lower().split())


async def detect_refunds(
    session: AsyncSession,
    household_id: uuid.UUID,
    lookback_days: int = 90,
) -> int:
    """Scan recent transactions for same-account refund pairs.

    Returns the number of new pairs created. Rows already participating in a
    transfer or refund pair are skipped.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    result = await session.execute(
        select(Transaction)
        .where(
            Transaction.household_id == household_id,
            Transaction.transaction_date >= cutoff,
            Transaction.bank_account_id.is_not(None),
            Transaction.transfer_pair_id.is_(None),
            Transaction.refund_pair_id.is_(None),
        )
        .order_by(Transaction.transaction_date)
    )
    transactions = result.scalars().all()

    # Bucket by (bank_account_id, currency, merchant identity, abs amount cents).
    # Merchant identity prefers merchant_id (robust to Plaid raw-name variance
    # like "APPLE.COM/BILL" vs "APPLE*ITUNES") and falls back to the normalized
    # raw merchant name when no merchant_id has been linked yet.
    buckets: dict[tuple, list[Transaction]] = defaultdict(list)
    for tx in transactions:
        merchant_identity = (
            ("id", tx.merchant_id)
            if tx.merchant_id is not None
            else ("raw", _normalize_merchant(tx.raw_merchant_name))
        )
        key = (
            tx.bank_account_id,
            tx.currency,
            merchant_identity,
            round(abs(float(tx.amount)) * 100),
        )
        buckets[key].append(tx)

    matched_ids: set[uuid.UUID] = set()
    pairs_found = 0

    for candidates in buckets.values():
        if len(candidates) < 2:
            continue
        # Candidates are already globally ordered by transaction_date (query sort).
        for i, tx_a in enumerate(candidates):
            if tx_a.id in matched_ids:
                continue
            if tx_a.amount >= 0:
                # We only start pairs from the negative (charge) side — this way,
                # the earliest-refund rule for a given charge is a natural
                # consequence of iterating candidates in date order.
                continue

            for tx_b in candidates[i + 1 :]:
                if tx_b.id in matched_ids:
                    continue
                # Opposite signs — tx_a is negative, need tx_b positive.
                if tx_b.amount <= 0:
                    continue
                # Refund must be 0–90 days AFTER the charge.
                delta = tx_b.transaction_date - tx_a.transaction_date
                if delta < timedelta(days=0) or delta > timedelta(days=90):
                    continue

                pair_id = uuid.uuid4()
                await session.execute(
                    update(Transaction)
                    .where(Transaction.id.in_([tx_a.id, tx_b.id]))
                    .values(refund_pair_id=pair_id)
                )
                matched_ids.add(tx_a.id)
                matched_ids.add(tx_b.id)
                pairs_found += 1
                break

    return pairs_found
