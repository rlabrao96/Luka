"""Shared email dedup-and-enrich logic for both Plaid and luka-connect sync.

When a bank sync transaction matches an email transaction:
1. Copy enrichment data (merchant_id, account_type, splits, custom merchant name)
2. Apply to the bank transaction
3. Delete the email transaction

Matching priority:
1. Exact: same merchant, ±2 days, exact amount
2. Fuzzy: same merchant, ±3 days, amount within 30%
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
) -> None:
    """Apply enrichment from email tx to bank tx, re-link splits, delete email txs."""
    # Apply enrichment fields to bank transaction
    update_fields = {}
    if enrichment.get("merchant_id"):
        update_fields["merchant_id"] = enrichment["merchant_id"]
    if enrichment.get("category"):
        update_fields["category"] = enrichment["category"]
    if enrichment.get("transaction_type") and enrichment["transaction_type"] != "expense":
        update_fields["transaction_type"] = enrichment["transaction_type"]

    if update_fields:
        await session.execute(
            update(Transaction).where(Transaction.id == bank_tx_id).values(**update_fields)
        )

    # Re-link any transaction_splits from email txs to the bank tx
    for email_id in email_tx_ids:
        await session.execute(
            update(TransactionSplit)
            .where(TransactionSplit.transaction_id == email_id)
            .values(transaction_id=bank_tx_id)
        )

    # Delete email transactions
    await session.execute(delete(Transaction).where(Transaction.id.in_(email_tx_ids)))


async def _find_single_match(
    session: AsyncSession,
    user_id: uuid.UUID,
    raw_merchant_name: str,
    amount: float,
    tx_date,
    day_window: int,
    amount_tolerance: float,
) -> Transaction | None:
    """Find a single email transaction matching by merchant, date window, and amount tolerance."""
    date_min = tx_date - timedelta(days=day_window)
    date_max = tx_date + timedelta(days=day_window)

    conditions = [
        Transaction.user_id == user_id,
        Transaction.source_type == "email",
        Transaction.transaction_date >= date_min,
        Transaction.transaction_date <= date_max,
        Transaction.raw_merchant_name.ilike(
            f"%{raw_merchant_name.replace('%', r'\%').replace('_', r'\_')}%"
        )
        if raw_merchant_name
        else True,
    ]

    if amount_tolerance == 0.0:
        conditions.append(Transaction.amount == amount)
    else:
        abs_amount = abs(amount)
        lower = abs_amount * (1 - amount_tolerance)
        upper = abs_amount * (1 + amount_tolerance)
        from sqlalchemy import func as sa_func

        conditions.append(sa_func.abs(Transaction.amount) >= lower)
        conditions.append(sa_func.abs(Transaction.amount) <= upper)
        # Same sign
        if amount < 0:
            conditions.append(Transaction.amount < 0)
        else:
            conditions.append(Transaction.amount > 0)

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
) -> dict | None:
    """Find N email transactions from same merchant whose sum matches the bank amount."""
    date_min = tx_date - timedelta(days=day_window)
    date_max = tx_date + timedelta(days=day_window)

    merchant_condition = (
        Transaction.raw_merchant_name.ilike(
            f"%{raw_merchant_name.replace('%', r'\%').replace('_', r'\_')}%"
        )
        if raw_merchant_name
        else True
    )
    result = await session.execute(
        select(Transaction)
        .where(
            Transaction.user_id == user_id,
            Transaction.source_type == "email",
            Transaction.transaction_date >= date_min,
            Transaction.transaction_date <= date_max,
            merchant_condition,
        )
        .order_by(Transaction.amount.desc())
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


async def _extract_enrichment(session: AsyncSession, email_tx_id: uuid.UUID) -> dict:
    """Extract enrichment data from an email transaction."""
    result = await session.execute(select(Transaction).where(Transaction.id == email_tx_id))
    tx = result.scalar_one_or_none()
    if not tx:
        return {}

    return {
        "merchant_id": tx.merchant_id,
        "category": tx.category,
        "transaction_type": tx.transaction_type,
        "account_type": getattr(tx, "account_type", None),  # personal/joint from splits
    }
