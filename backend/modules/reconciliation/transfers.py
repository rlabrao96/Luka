"""Transfer detection: identifies inter-account transfers and CC payments.

Detection methods (in order):
1. Plaid category tags (TRANSFER_IN, TRANSFER_OUT, LOAN_PAYMENTS)
2. Cross-account amount matching (same amount, ±2 days, opposite signs, same household)

Bank-only rule
--------------
A transfer pair is a real money movement between two bank accounts. Email rows
are bank-notification echoes — they describe the same movement but are not the
movement itself. Pairing an email row with a Plaid/Connect row as a "transfer"
double-classifies a single side, so we restrict candidates strictly to
``source_type IN ('plaid', 'connect')``.

Orphan healing
--------------
When one leg of a paired row is deleted (manually, via cleanup script, or via
``delete_transaction``), the partner can end up holding a ``transfer_pair_id``
or ``refund_pair_id`` that no other row holds — orphaned. ``detect_transfers``
runs a healing pass at the start of every tick that nulls those orphan ids so
the row becomes eligible for re-pairing on the same scan.

When detected, both transactions get transaction_type="transfer" and a shared
transfer_pair_id.
"""

import uuid
from collections import defaultdict
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from modules.transactions.models import Transaction


# Source types that represent actual money movement (vs. email notifications).
# Only these are eligible to form transfer/refund pairs.
BANK_SOURCE_TYPES = ("plaid", "connect")


async def _heal_orphan_pair_ids(session: AsyncSession, household_id: uuid.UUID) -> tuple[int, int]:
    """Null out transfer_pair_id / refund_pair_id values that are held by
    exactly one row globally for this household.

    Globally scoped (no date filter) on the count side so we don't accidentally
    clear a pair_id whose twin sits outside the lookback window. Clear is then
    applied to the surviving single rows. Returns (transfers_healed,
    refunds_healed).
    """
    healed_transfers = 0
    healed_refunds = 0

    for column in (Transaction.transfer_pair_id, Transaction.refund_pair_id):
        # Find pair_ids that exist on exactly one row in this household.
        orphan_rows = (
            (
                await session.execute(
                    select(column)
                    .where(
                        Transaction.household_id == household_id,
                        column.is_not(None),
                    )
                    .group_by(column)
                    .having(func.count() == 1)
                )
            )
            .scalars()
            .all()
        )

        if not orphan_rows:
            continue

        result = await session.execute(
            update(Transaction)
            .where(
                Transaction.household_id == household_id,
                column.in_(orphan_rows),
            )
            .values({column: None})
        )
        if column is Transaction.transfer_pair_id:
            healed_transfers = result.rowcount or len(orphan_rows)
        else:
            healed_refunds = result.rowcount or len(orphan_rows)

    if healed_transfers or healed_refunds:
        print(
            f"[transfers] healed orphan pair_ids: "
            f"transfers={healed_transfers} refunds={healed_refunds} "
            f"household={household_id}",
            flush=True,
        )

    return healed_transfers, healed_refunds


async def detect_transfers(
    session: AsyncSession,
    household_id: uuid.UUID,
    lookback_days: int = 5,
) -> int:
    """Scan recent bank transactions for transfer pairs.

    Only ``source_type IN ('plaid','connect')`` rows are candidates — email
    rows are notifications, never the actual movement, and pairing them would
    double-classify one side of a transfer.

    Heals orphan ``transfer_pair_id`` / ``refund_pair_id`` values (held by
    exactly one row) before scanning, so previously-paired rows whose twin
    was deleted become eligible to re-pair.

    Returns the number of pairs detected.
    """
    from datetime import datetime, timezone

    # ---------- 0. Heal orphan pair_ids first so freshly-unpaired rows are eligible.
    await _heal_orphan_pair_ids(session, household_id)

    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    pairs_found = 0

    # Get all recent non-paired bank-sourced transactions for this household.
    # Email rows are excluded — they are notifications, not the money movement.
    result = await session.execute(
        select(Transaction)
        .where(
            Transaction.household_id == household_id,
            Transaction.transaction_date >= cutoff,
            Transaction.transfer_pair_id.is_(None),
            Transaction.refund_pair_id.is_(None),
            Transaction.source_type.in_(BANK_SOURCE_TYPES),
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

                # Within ±2 days (abs of the full timedelta — flooring
                # negative .days first made the window asymmetric by row order)
                if abs(tx_a.transaction_date - tx_b.transaction_date) > timedelta(days=2):
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

    Bank-only: both ``bank_tx`` and any candidate twin must have
    ``source_type IN ('plaid','connect')``. Email rows are echoes of the
    movement, never the movement itself, and must never form a transfer pair.
    Called on an email-sourced row, this returns ``None`` immediately.

    Returns the new transfer_pair_id on success, or None if no twin exists or
    the input row is not bank-sourced.
    """
    bank_tx = (
        await session.execute(select(Transaction).where(Transaction.id == bank_tx_id))
    ).scalar_one_or_none()
    if bank_tx is None or bank_tx.bank_account_id is None:
        return None
    # Bank-only guard: refuse to pair email rows.
    if bank_tx.source_type not in BANK_SOURCE_TYPES:
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
                    Transaction.source_type.in_(BANK_SOURCE_TYPES),
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
