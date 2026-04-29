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

from modules.households.models import BankAccount
from modules.transactions.models import Transaction, TransactionSplit


def _resolve_vendor_name(
    *,
    bank: Transaction,
    email_name: str | None,
    bank_marker: bool,
    email_marker: bool,
) -> tuple[str | None, bool]:
    """Pick the canonical raw_merchant_name when consolidating email + bank rows.

    User-edit-wins: whichever side has the merchant_name marker wins. If both
    sides claim it, the bank row's marker wins (it's the survivor of the merge).
    Otherwise prefer Plaid's enriched name (already on `bank.raw_merchant_name`
    via `mapper.map_plaid_transaction`, which prefers `merchant_name` over
    `name`). Falls back to the email's parsed merchant when Plaid has nothing.

    Returns (resolved_name, propagate_marker_to_bank).
    """
    if bank_marker:
        return bank.raw_merchant_name, True
    if email_marker and email_name:
        return email_name, True
    if bank.raw_merchant_name and bank.raw_merchant_name.strip().lower() not in ("", "unknown"):
        return bank.raw_merchant_name, False
    if email_name:
        return email_name, False
    return bank.raw_merchant_name, False


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
    # Load the bank row so we can compare its user_edited_fields against the
    # email's. User-edit-wins: a field marked on the bank row is never
    # overwritten; a field marked on the email row wins and propagates its
    # marker forward.
    bank_row = await session.scalar(select(Transaction).where(Transaction.id == bank_tx_id))
    if bank_row is None:
        return
    bank_marks = dict(bank_row.user_edited_fields or {})
    email_marks = dict(enrichment.get("user_edited_fields") or {})

    def _bank_owns(field: str) -> bool:
        return bool(bank_marks.get(field))

    def _email_owns(field: str) -> bool:
        return bool(email_marks.get(field))

    new_marks = dict(bank_marks)
    update_fields: dict = {}
    incoming_type = enrichment.get("transaction_type")

    # --- merchant_id: piggy-backs on merchant_name ownership.
    if enrichment.get("merchant_id") and not _bank_owns("merchant_name"):
        update_fields["merchant_id"] = enrichment["merchant_id"]

    # --- transfer_to_account_id
    if not _bank_owns("transfer_to_account_id"):
        if _email_owns("transfer_to_account_id"):
            update_fields["transfer_to_account_id"] = enrichment.get("transfer_to_account_id")
            new_marks["transfer_to_account_id"] = True
        elif enrichment.get("transfer_to_account_id"):
            update_fields["transfer_to_account_id"] = enrichment["transfer_to_account_id"]

    # --- transaction_type / category
    if incoming_type == "transfer" and not _bank_owns("transaction_type"):
        # Transfers always propagate type=transfer and null out stale category
        # (CC-payment emails often carry a heuristic category that's wrong),
        # UNLESS the user has explicitly edited those fields on the bank row.
        update_fields["transaction_type"] = "transfer"
        if not _bank_owns("category"):
            update_fields["category"] = None
    else:
        if not _bank_owns("category"):
            if _email_owns("category"):
                # User explicitly set (or cleared) category on email row — copy
                # even if NULL.
                update_fields["category"] = enrichment.get("category")
                new_marks["category"] = True
            elif enrichment.get("category"):
                update_fields["category"] = enrichment["category"]
        if not _bank_owns("transaction_type"):
            if _email_owns("transaction_type"):
                update_fields["transaction_type"] = incoming_type
                new_marks["transaction_type"] = True
            elif incoming_type and incoming_type != "expense":
                update_fields["transaction_type"] = incoming_type

    # --- raw_merchant_name (Plaid-enriched usually wins; user edits always win)
    resolved_name, propagate_name_mark = _resolve_vendor_name(
        bank=bank_row,
        email_name=enrichment.get("raw_merchant_name"),
        bank_marker=_bank_owns("merchant_name"),
        email_marker=_email_owns("merchant_name"),
    )
    if resolved_name and resolved_name != bank_row.raw_merchant_name:
        update_fields["raw_merchant_name"] = resolved_name
    if propagate_name_mark:
        new_marks["merchant_name"] = True

    # Persist marker map if it grew.
    if new_marks != bank_marks:
        update_fields["user_edited_fields"] = new_marks

    if update_fields:
        await session.execute(
            update(Transaction).where(Transaction.id == bank_tx_id).values(**update_fields)
        )

    # --- split_type (joint-account override is non-negotiable)
    is_joint = False
    if bank_row.bank_account_id is not None:
        account_type = await session.scalar(
            select(BankAccount.account_type).where(BankAccount.id == bank_row.bank_account_id)
        )
        is_joint = account_type == "joint"

    incoming_split = enrichment.get("split_type")
    if is_joint:
        target_split: str | None = "shared"
    elif _bank_owns("split_type"):
        target_split = None  # leave bank row's split untouched
    elif _email_owns("split_type") and incoming_split:
        target_split = incoming_split
    elif incoming_split:
        target_split = incoming_split
    else:
        target_split = None

    if target_split is not None:
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
                .values(split_type=target_split)
            )
        else:
            session.add(
                TransactionSplit(
                    id=uuid.uuid4(),
                    transaction_id=bank_tx_id,
                    split_type=target_split,
                )
            )
        # If the email-row owned the split_type marker, propagate it now that
        # we've written the value. (Joint override does NOT carry the marker —
        # it's a system rule, not a user decision.)
        if not is_joint and _email_owns("split_type") and not _bank_owns("split_type"):
            current = await session.scalar(
                select(Transaction.user_edited_fields).where(Transaction.id == bank_tx_id)
            )
            current = dict(current or {})
            if not current.get("split_type"):
                current["split_type"] = True
                await session.execute(
                    update(Transaction)
                    .where(Transaction.id == bank_tx_id)
                    .values(user_edited_fields=current)
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
        "raw_merchant_name": tx.raw_merchant_name,
        "user_edited_fields": dict(tx.user_edited_fields or {}),
    }
