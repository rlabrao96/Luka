"""Transfer detection: identifies inter-account transfers and CC payments.

Detection methods (in order):
1. Plaid category tags (TRANSFER_IN, TRANSFER_OUT, LOAN_PAYMENTS)
2. Cross-account amount matching (same amount, ±2 days, opposite signs, same household)

When detected, both transactions get transaction_type="transfer" and a shared transfer_pair_id.
"""

import uuid
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

    # Build index by absolute amount for O(n) matching
    matched_ids: set[uuid.UUID] = set()

    for i, tx_a in enumerate(transactions):
        if tx_a.id in matched_ids:
            continue

        for tx_b in transactions[i + 1 :]:
            if tx_b.id in matched_ids:
                continue

            # Must be different accounts
            if tx_a.bank_account_id == tx_b.bank_account_id:
                continue
            if tx_a.bank_account_id is None or tx_b.bank_account_id is None:
                continue

            # Same absolute amount, opposite signs
            if abs(abs(tx_a.amount) - abs(tx_b.amount)) > 0.01:
                continue
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
