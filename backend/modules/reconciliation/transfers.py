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

    # Get all recent non-transfer transactions for this household. Rows already
    # typed 'transfer' are handled separately via pair_transfer_twin so we don't
    # accidentally re-pair a just-linked Vincular row with an unrelated match.
    result = await session.execute(
        select(Transaction)
        .where(
            Transaction.household_id == household_id,
            Transaction.transaction_type != "transfer",
            Transaction.transaction_date >= cutoff,
            Transaction.transfer_pair_id.is_(None),
            Transaction.refund_pair_id.is_(None),
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

                # Same owner — transfers are own-account moves, never cross-member.
                if tx_a.user_id != tx_b.user_id:
                    continue

                # Same currency — CLP 10.000 and USD 10.000 are not a pair.
                if tx_a.currency != tx_b.currency:
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


async def pair_transfer_twin(
    session: AsyncSession,
    bank_tx_id: uuid.UUID,
    day_window: int = 2,
) -> uuid.UUID | None:
    """Find and link the opposite-leg twin of a single transfer transaction.

    Used after manual Vincular so the linked bank row (already typed
    'transfer') gets paired with its twin on another account. Scoped to one
    bank_tx — avoids the broad rescan that could mis-pair unrelated rows.

    Returns the new transfer_pair_id on success, or None if no twin exists.
    """
    bank_tx = (
        await session.execute(select(Transaction).where(Transaction.id == bank_tx_id))
    ).scalar_one_or_none()
    if bank_tx is None or bank_tx.bank_account_id is None:
        return None
    if bank_tx.transfer_pair_id is not None:
        return bank_tx.transfer_pair_id

    window_start = bank_tx.transaction_date - timedelta(days=day_window)
    window_end = bank_tx.transaction_date + timedelta(days=day_window)
    amount_cents = round(abs(float(bank_tx.amount)) * 100)

    candidates = (
        (
            await session.execute(
                select(Transaction).where(
                    Transaction.household_id == bank_tx.household_id,
                    Transaction.user_id == bank_tx.user_id,
                    Transaction.currency == bank_tx.currency,
                    Transaction.id != bank_tx.id,
                    Transaction.bank_account_id.is_not(None),
                    Transaction.bank_account_id != bank_tx.bank_account_id,
                    Transaction.transfer_pair_id.is_(None),
                    Transaction.refund_pair_id.is_(None),
                    Transaction.transaction_date.between(window_start, window_end),
                )
            )
        )
        .scalars()
        .all()
    )

    # Prefer the closest date match; break ties with opposite-sign exact amount.
    twin: Transaction | None = None
    best_delta = timedelta(days=day_window + 1)
    for c in candidates:
        if (c.amount > 0) == (bank_tx.amount > 0):
            continue  # must be opposite sign
        if round(abs(float(c.amount)) * 100) != amount_cents:
            continue
        delta = abs(c.transaction_date - bank_tx.transaction_date)
        if delta < best_delta:
            twin = c
            best_delta = delta

    if twin is None:
        return None

    pair_id = uuid.uuid4()
    await session.execute(
        update(Transaction)
        .where(Transaction.id.in_([bank_tx.id, twin.id]))
        .values(transaction_type="transfer", transfer_pair_id=pair_id)
    )
    return pair_id
