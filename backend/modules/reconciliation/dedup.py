"""Shared email dedup-and-enrich logic for both Plaid and luka-connect sync.

When a bank sync transaction matches an email transaction:
1. Copy enrichment data (merchant_id, account_type, splits, custom merchant name)
2. Apply to the bank transaction
3. Delete the email transaction

Matching priority:
1. Exact: same merchant (unless transfer), ±2 days, exact signed amount, same currency
2. Fuzzy: same merchant (unless transfer), ±3 days, amount within 30% (same sign)
3. Sum: same merchant, ±3 days, sum of N email txs within 5%
"""

import uuid
from datetime import timedelta

from sqlalchemy import and_, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from modules.transactions.models import Transaction, TransactionSplit


async def find_email_match(
    session: AsyncSession,
    user_id: uuid.UUID,
    raw_merchant_name: str,
    amount: float,
    tx_date,
    source_bank_name: str | None = None,
    currency: str | None = None,
    incoming_transaction_type: str | None = None,
    bank_account_id: uuid.UUID | None = None,
) -> dict | None:
    """Find matching email transaction(s) using 3-tier priority.

    Returns dict with:
      - match_type: "exact" | "fuzzy" | "sum"
      - email_tx_ids: list of matched email transaction IDs
      - enrichment: dict of fields to copy to bank tx
    Or None if no match found.
    """
    abs_amount = abs(amount)

    # --- Priority 1: Exact match ---
    exact_match = await _find_single_match(
        session,
        user_id,
        raw_merchant_name,
        amount,
        tx_date,
        day_window=2,
        amount_tolerance=0.0,
        currency=currency,
        incoming_transaction_type=incoming_transaction_type,
        bank_account_id=bank_account_id,
    )
    if exact_match:
        enrichment = await _extract_enrichment(session, exact_match.id)
        return {"match_type": "exact", "email_tx_ids": [exact_match.id], "enrichment": enrichment}

    # --- Priority 2: Fuzzy match (within 30%) ---
    fuzzy_match = await _find_single_match(
        session,
        user_id,
        raw_merchant_name,
        amount,
        tx_date,
        day_window=3,
        amount_tolerance=0.30,
        currency=currency,
        incoming_transaction_type=incoming_transaction_type,
        bank_account_id=bank_account_id,
    )
    if fuzzy_match:
        enrichment = await _extract_enrichment(session, fuzzy_match.id)
        return {"match_type": "fuzzy", "email_tx_ids": [fuzzy_match.id], "enrichment": enrichment}

    # --- Priority 3: Sum match (N email txs sum to bank amount, within 5%) ---
    sum_result = await _find_sum_match(
        session,
        user_id,
        raw_merchant_name,
        abs_amount,
        tx_date,
        day_window=3,
        sum_tolerance=0.05,
        currency=currency,
        incoming_sign=(1 if amount >= 0 else -1),
        bank_account_id=bank_account_id,
    )
    if sum_result:
        # Use enrichment from the largest email tx
        primary_tx_id = sum_result["primary_tx_id"]
        enrichment = await _extract_enrichment(session, primary_tx_id)
        return {"match_type": "sum", "email_tx_ids": sum_result["tx_ids"], "enrichment": enrichment}

    return None


async def apply_match_and_delete_emails(
    session: AsyncSession,
    bank_tx_id: uuid.UUID,
    email_tx_ids: list[uuid.UUID],
    enrichment: dict,
    user_id: uuid.UUID,
) -> None:
    """Apply enrichment from email tx to bank tx, re-link splits, delete email txs.

    `user_id` scopes the split re-link and email delete to the owner of the bank
    tx — defense in depth even though the sole caller is already user-scoped.
    """
    # Apply enrichment fields to bank transaction.
    # Transfers always propagate: transaction_type='transfer' and category=NULL
    # (CC-payment emails often carry a stale category from heuristics).
    update_fields: dict = {}
    incoming_type = enrichment.get("transaction_type")
    if enrichment.get("merchant_id"):
        update_fields["merchant_id"] = enrichment["merchant_id"]
    if enrichment.get("transfer_to_account_id"):
        update_fields["transfer_to_account_id"] = enrichment["transfer_to_account_id"]
    if incoming_type == "transfer":
        # Transfers always propagate: type=transfer and null out stale category
        update_fields["transaction_type"] = "transfer"
        update_fields["category"] = None
    else:
        if enrichment.get("category"):
            update_fields["category"] = enrichment["category"]
        if incoming_type and incoming_type != "expense":
            update_fields["transaction_type"] = incoming_type

    if update_fields:
        await session.execute(
            update(Transaction).where(Transaction.id == bank_tx_id).values(**update_fields)
        )

    # Propagate the email's split_type onto the bank row's existing split so the
    # user's personal/shared decision is preserved. If the bank row has no split,
    # create one; if it already has one, update it in place.
    incoming_split = enrichment.get("split_type")
    if incoming_split:
        existing_split = await session.execute(
            select(TransactionSplit.id)
            .where(TransactionSplit.transaction_id == bank_tx_id)
            .limit(1)
        )
        split_id = existing_split.scalar_one_or_none()
        if split_id:
            await session.execute(
                update(TransactionSplit)
                .where(TransactionSplit.id == split_id)
                .values(split_type=incoming_split)
            )
        else:
            session.add(
                TransactionSplit(
                    id=uuid.uuid4(),
                    transaction_id=bank_tx_id,
                    split_type=incoming_split,
                )
            )

    # Delete the email rows (and their splits via FK or explicit delete).
    if email_tx_ids:
        # Delete email splits first to avoid orphaning; bank already has its own.
        await session.execute(
            delete(TransactionSplit).where(
                TransactionSplit.transaction_id.in_(
                    select(Transaction.id).where(
                        Transaction.id.in_(email_tx_ids),
                        Transaction.user_id == user_id,
                    )
                )
            )
        )

        # Delete email transactions (user-scoped)
        await session.execute(
            delete(Transaction).where(
                Transaction.id.in_(email_tx_ids),
                Transaction.user_id == user_id,
            )
        )


async def _find_single_match(
    session: AsyncSession,
    user_id: uuid.UUID,
    raw_merchant_name: str,
    amount: float,
    tx_date,
    day_window: int,
    amount_tolerance: float,
    currency: str | None = None,
    incoming_transaction_type: str | None = None,
    bank_account_id: uuid.UUID | None = None,
) -> Transaction | None:
    """Find a single email transaction matching by merchant, date window, and amount tolerance.

    Filters:
      - currency equality (when `currency` is provided)
      - signed-amount equality (opposite signs never match — +27.43 vs -27.43 are
        different events: income vs expense)
      - bank_account_id equality when both sides have one (candidate may be null
        if the email row hasn't been resolved to a bank account yet)
      - merchant ILIKE filter is skipped for transfers (CC-payment emails carry
        strings like "Pago Tarjeta ****3100" while Plaid has "American Express")
    """
    date_min = tx_date - timedelta(days=day_window)
    date_max = tx_date + timedelta(days=day_window)

    conditions = [
        Transaction.user_id == user_id,
        Transaction.source_type == "email",
        Transaction.transaction_date >= date_min,
        Transaction.transaction_date <= date_max,
    ]

    # Currency equality — CLP 2.000 must never match USD 2.000
    if currency is not None:
        conditions.append(Transaction.currency == currency)

    # Merchant ILIKE — skip entirely for transfers (divergent strings)
    if incoming_transaction_type != "transfer" and raw_merchant_name:
        conditions.append(
            Transaction.raw_merchant_name.ilike(
                f"%{raw_merchant_name.replace('%', r'\%').replace('_', r'\_')}%"
            )
        )

    # bank_account_id parity when both are set
    if bank_account_id is not None:
        conditions.append(
            (Transaction.bank_account_id == bank_account_id)
            | (Transaction.bank_account_id.is_(None))
        )

    # Signed amount equality (not abs) — same sign convention on both sides
    if amount_tolerance == 0.0:
        conditions.append(Transaction.amount == amount)
    elif amount >= 0:
        lower = amount * (1 - amount_tolerance)
        upper = amount * (1 + amount_tolerance)
        conditions.append(Transaction.amount >= lower)
        conditions.append(Transaction.amount <= upper)
    else:
        # amount is negative — tolerance widens toward more-negative & less-negative
        lower = amount * (1 + amount_tolerance)  # more negative
        upper = amount * (1 - amount_tolerance)  # less negative (closer to 0)
        conditions.append(Transaction.amount >= lower)
        conditions.append(Transaction.amount <= upper)

    result = await session.execute(select(Transaction).where(and_(*conditions)).limit(1))
    return result.scalar_one_or_none()


async def _find_sum_match(
    session: AsyncSession,
    user_id: uuid.UUID,
    raw_merchant_name: str,
    abs_amount: float,
    tx_date,
    day_window: int,
    sum_tolerance: float,
    currency: str | None = None,
    incoming_sign: int = -1,
    bank_account_id: uuid.UUID | None = None,
) -> dict | None:
    """Find N email transactions from same merchant whose sum matches the bank amount."""
    date_min = tx_date - timedelta(days=day_window)
    date_max = tx_date + timedelta(days=day_window)

    conditions = [
        Transaction.user_id == user_id,
        Transaction.source_type == "email",
        Transaction.transaction_date >= date_min,
        Transaction.transaction_date <= date_max,
    ]
    if currency is not None:
        conditions.append(Transaction.currency == currency)
    if raw_merchant_name:
        conditions.append(
            Transaction.raw_merchant_name.ilike(
                f"%{raw_merchant_name.replace('%', r'\%').replace('_', r'\_')}%"
            )
        )
    if bank_account_id is not None:
        conditions.append(
            (Transaction.bank_account_id == bank_account_id)
            | (Transaction.bank_account_id.is_(None))
        )
    # Only consider candidates with the same sign as the incoming bank tx
    if incoming_sign >= 0:
        conditions.append(Transaction.amount >= 0)
    else:
        conditions.append(Transaction.amount <= 0)

    result = await session.execute(
        select(Transaction).where(and_(*conditions)).order_by(Transaction.amount.desc())
    )
    candidates = result.scalars().all()

    if len(candidates) < 2:
        return None

    total = sum(abs(c.amount) for c in candidates)
    lower = abs_amount * (1 - sum_tolerance)
    upper = abs_amount * (1 + sum_tolerance)

    if lower <= total <= upper:
        # Find the largest tx for enrichment source
        primary = max(candidates, key=lambda c: abs(c.amount))
        return {
            "tx_ids": [c.id for c in candidates],
            "primary_tx_id": primary.id,
        }

    return None


async def find_plaid_match_for_email(
    session: AsyncSession,
    email_tx: Transaction,
) -> Transaction | None:
    """Direction-symmetric counterpart to find_email_match.

    Given a pending email-source transaction, find an already-settled Plaid
    bank transaction that represents the same event. Used by the periodic
    reconciliation tick for the case where the Plaid webhook beat the email
    (or where the email arrived during a window when no direct match ran).

    Filters:
      - same owner (user_id)
      - source_type='plaid', status='settled'
      - currency equality
      - signed amount equality (expenses stay negative, income positive)
      - transaction_date within ±3 days of the email date
      - not already paired in a transfer or refund
      - bank_account_id parity when both sides are set; prefer the
        transfer_to_account_id when the email is a CC-payment transfer
      - merchant ILIKE filter skipped for transfers (CC payment strings
        diverge from Plaid's institution label)
    """
    date_min = email_tx.transaction_date - timedelta(days=3)
    date_max = email_tx.transaction_date + timedelta(days=3)

    conditions = [
        Transaction.user_id == email_tx.user_id,
        Transaction.source_type == "plaid",
        Transaction.status == "settled",
        Transaction.currency == email_tx.currency,
        Transaction.amount == email_tx.amount,
        Transaction.transaction_date >= date_min,
        Transaction.transaction_date <= date_max,
        Transaction.transfer_pair_id.is_(None),
        Transaction.refund_pair_id.is_(None),
    ]

    is_transfer = email_tx.transaction_type == "transfer"

    # Merchant filter — skip for transfers where the strings diverge.
    if not is_transfer and email_tx.raw_merchant_name:
        safe = email_tx.raw_merchant_name.replace("%", r"\%").replace("_", r"\_")
        conditions.append(Transaction.raw_merchant_name.ilike(f"%{safe}%"))

    # Bank account parity.
    preferred_account_id = None
    if is_transfer and email_tx.transfer_to_account_id is not None:
        # For CC-payment emails, the Plaid row lives on the card (transfer_to).
        preferred_account_id = email_tx.transfer_to_account_id
    elif email_tx.bank_account_id is not None:
        preferred_account_id = email_tx.bank_account_id

    if preferred_account_id is not None:
        conditions.append(
            (Transaction.bank_account_id == preferred_account_id)
            | (Transaction.bank_account_id.is_(None))
        )

    # Order by date proximity (closest first). Simple ABS trick via two-sided ordering
    # isn't trivial in SQL; ordering by date ascending then picking the first within
    # the symmetric window is good-enough for a first pass.
    result = await session.execute(
        select(Transaction).where(and_(*conditions)).order_by(Transaction.transaction_date)
    )
    candidates = result.scalars().all()
    if not candidates:
        return None

    # Pick the candidate whose date is closest to the email date.
    return min(
        candidates,
        key=lambda c: abs((c.transaction_date - email_tx.transaction_date).total_seconds()),
    )


async def _extract_enrichment(session: AsyncSession, email_tx_id: uuid.UUID) -> dict:
    """Extract enrichment data from an email transaction.

    Pulls the full set of user-meaningful fields so a manual Vincular truly
    transfers the pending's classification onto the bank row: category,
    merchant, transaction_type, split_type, and (for CC-payment emails that
    resolved a counterpart) transfer_to_account_id.
    """
    result = await session.execute(select(Transaction).where(Transaction.id == email_tx_id))
    tx = result.scalar_one_or_none()
    if not tx:
        return {}

    # Pick up the email's split (if any) — user may have already set personal/shared.
    split_row = await session.execute(
        select(TransactionSplit.split_type)
        .where(TransactionSplit.transaction_id == email_tx_id)
        .limit(1)
    )
    split_type = split_row.scalar_one_or_none()

    return {
        "merchant_id": tx.merchant_id,
        "category": tx.category,
        "transaction_type": tx.transaction_type,
        "split_type": split_type,
        "transfer_to_account_id": tx.transfer_to_account_id,
    }
