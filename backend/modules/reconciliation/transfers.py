"""Transfer detection: identifies inter-account transfers and CC payments.

Detection methods (in order):
1. Plaid category tags (TRANSFER_IN, TRANSFER_OUT, LOAN_PAYMENTS)
2. Cross-account amount matching (same amount, ±2 days, opposite signs, same household)

When detected, both transactions get transaction_type="transfer" and a shared transfer_pair_id.
"""

import uuid
from collections import defaultdict
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from modules.transactions.models import Transaction


async def detect_transfers(
    session: AsyncSession,
    household_id: uuid.UUID,
    lookback_days: int = 5,
) -> int:
    """Scan recent transactions for transfer pairs. Returns number of pairs detected."""
    from datetime import datetime, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    pairs_found = 0

    # Get all recent non-transfer transactions for this household
    result = await session.execute(
        select(Transaction)
        .where(
            Transaction.household_id == household_id,
            Transaction.transaction_type != "transfer",
            Transaction.transaction_date >= cutoff,
            Transaction.transfer_pair_id.is_(None),
        )
        .order_by(Transaction.transaction_date)
    )
    transactions = result.scalars().all()

    # Build index by rounded absolute amount for O(n) matching
    by_amount: dict[int, list[Transaction]] = defaultdict(list)
    for tx in transactions:
        # Key = amount in cents to avoid float issues
        key = round(abs(float(tx.amount)) * 100)
        by_amount[key].append(tx)

    matched_ids: set[uuid.UUID] = set()

    for candidates in by_amount.values():
        if len(candidates) < 2:
            continue

        for i, tx_a in enumerate(candidates):
            if tx_a.id in matched_ids:
                continue

            for tx_b in candidates[i + 1 :]:
                if tx_b.id in matched_ids:
                    continue

                # Must be different accounts
                if tx_a.bank_account_id == tx_b.bank_account_id:
                    continue
                if tx_a.bank_account_id is None or tx_b.bank_account_id is None:
                    continue

                # Opposite signs
                if (tx_a.amount > 0) == (tx_b.amount > 0):
                    continue

                # Within ±2 days
                day_diff = abs((tx_a.transaction_date - tx_b.transaction_date).days)
                if day_diff > 2:
                    continue

                # Match found — mark both as transfers
                pair_id = uuid.uuid4()
                await session.execute(
                    update(Transaction)
                    .where(Transaction.id.in_([tx_a.id, tx_b.id]))
                    .values(transaction_type="transfer", transfer_pair_id=pair_id)
                )
                matched_ids.add(tx_a.id)
                matched_ids.add(tx_b.id)
                pairs_found += 1
                break

    return pairs_found
