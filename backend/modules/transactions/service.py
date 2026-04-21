import uuid
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, text, delete as sql_delete, update as sql_update
from modules.transactions.models import Transaction, TransactionSplit
from modules.households.models import BankAccount, HouseholdMember
from modules.merchants.models import Merchant
from modules.merchant_review.models import CanonicalMerchant
from modules.merchants.service import record_category_selection
from core.cache import _get_redis


async def get_my_transactions(db: AsyncSession, user_id: uuid.UUID, since: date) -> list[dict]:
    result = await db.execute(
        select(
            Transaction,
            TransactionSplit,
            BankAccount.bank_name,
            BankAccount.account_kind,
            CanonicalMerchant.display_name.label("display_name"),
        )
        .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
        .outerjoin(Merchant, Transaction.raw_merchant_name == Merchant.raw_name)
        .outerjoin(CanonicalMerchant, Merchant.canonical_merchant_id == CanonicalMerchant.id)
        .where(
            Transaction.user_id == user_id,
            Transaction.transaction_date >= since,
            Transaction.status.notin_(["pending", "orphan"]),
        )
        .order_by(Transaction.transaction_date.desc())
    )
    rows = result.all()
    return [
        {
            **{k: v for k, v in vars(txn).items() if not k.startswith("_")},
            "split_type": split.split_type if split else None,
            "bank_name": bank_name or txn.source_bank_name,
            "account_kind": account_kind,
            "display_name": display_name,
        }
        for txn, split, bank_name, account_kind, display_name in rows
    ]


async def get_monthly_summary(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    currency: str | None = None,
) -> list[dict]:
    MONTH_ABBR = [
        "Ene",
        "Feb",
        "Mar",
        "Abr",
        "May",
        "Jun",
        "Jul",
        "Ago",
        "Sep",
        "Oct",
        "Nov",
        "Dic",
    ]
    # Currency filter: summing CLP and USD together produces nonsense.
    # When `currency` is provided (via the CLP/USD toggle), restrict both
    # aggregates to transactions in that currency.
    currency_clause = "AND t.currency = :currency" if currency else ""
    params: dict = {"household_id": str(household_id), "user_id": str(user_id)}
    if currency:
        params["currency"] = currency
    result = await db.execute(
        text(f"""
        WITH months AS (
            SELECT generate_series(
                DATE_TRUNC('month', NOW()) - INTERVAL '5 months',
                DATE_TRUNC('month', NOW()),
                INTERVAL '1 month'
            ) AS month_start
        ),
        personal_agg AS (
            SELECT
                DATE_TRUNC('month', t.transaction_date::DATE) AS month_start,
                COALESCE(SUM(t.amount), 0) AS personal
            FROM transactions t
            JOIN transaction_splits ts ON ts.transaction_id = t.id
            JOIN bank_accounts ba ON ba.id = t.bank_account_id AND ba.is_active = TRUE
            WHERE t.user_id = :user_id
              AND t.household_id = :household_id
              AND ts.split_type = 'personal'
              AND t.status NOT IN ('pending', 'orphan')
              AND t.transfer_pair_id IS NULL
              AND t.refund_pair_id IS NULL
              {currency_clause}
            GROUP BY DATE_TRUNC('month', t.transaction_date::DATE)
        ),
        shared_agg AS (
            SELECT
                DATE_TRUNC('month', t.transaction_date::DATE) AS month_start,
                COALESCE(SUM(t.amount), 0) AS compartido
            FROM transactions t
            JOIN transaction_splits ts ON ts.transaction_id = t.id
            JOIN bank_accounts ba ON ba.id = t.bank_account_id AND ba.is_active = TRUE
            WHERE t.household_id = :household_id
              AND ts.split_type = 'shared'
              AND t.status NOT IN ('pending', 'orphan')
              AND t.transfer_pair_id IS NULL
              AND t.refund_pair_id IS NULL
              {currency_clause}
            GROUP BY DATE_TRUNC('month', t.transaction_date::DATE)
        )
        SELECT
            m.month_start,
            COALESCE(p.personal, 0) AS personal,
            COALESCE(s.compartido, 0) AS compartido
        FROM months m
        LEFT JOIN personal_agg p ON p.month_start = m.month_start
        LEFT JOIN shared_agg s ON s.month_start = m.month_start
        ORDER BY m.month_start ASC
        """),
        params,
    )
    rows = result.all()
    return [
        {
            "month": f"{MONTH_ABBR[row.month_start.month - 1]} {str(row.month_start.year)[2:]}",
            "personal": float(row.personal),
            "compartido": float(row.compartido),
        }
        for row in rows
    ]


async def get_shared_transactions(
    db: AsyncSession, household_id: uuid.UUID, since: date
) -> list[dict]:
    result = await db.execute(
        select(
            Transaction,
            TransactionSplit,
            BankAccount.bank_name,
            CanonicalMerchant.display_name.label("display_name"),
        )
        .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
        .outerjoin(Merchant, Transaction.raw_merchant_name == Merchant.raw_name)
        .outerjoin(CanonicalMerchant, Merchant.canonical_merchant_id == CanonicalMerchant.id)
        .where(
            Transaction.household_id == household_id,
            TransactionSplit.split_type == "shared",
            Transaction.transaction_date >= since,
            Transaction.status.notin_(["pending", "orphan"]),
        )
        .order_by(Transaction.transaction_date.desc())
    )
    rows = result.all()
    return [
        {
            **{k: v for k, v in vars(txn).items() if not k.startswith("_")},
            "split_type": split.split_type,
            "bank_name": bank_name or txn.source_bank_name,
            "display_name": display_name,
        }
        for txn, split, bank_name, display_name in rows
    ]


async def update_category(
    db: AsyncSession, transaction_id: uuid.UUID, user_id: uuid.UUID, category: str | None
) -> bool:
    """Update transaction category. Returns False if transaction not found or not owned by user."""
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
        )
    )
    txn = result.scalar_one_or_none()
    if not txn:
        return False
    txn.category = category
    await db.commit()
    # Train merchant data: record this user correction for future suggestions
    if category:
        try:
            await record_category_selection(
                txn.raw_merchant_name, category, db, _get_redis(), user_id=user_id
            )
        except Exception:
            pass  # never block the category save if training fails
    return True


async def update_split_type(
    db: AsyncSession, transaction_id: uuid.UUID, user_id: uuid.UUID, split_type: str
) -> bool:
    """Update transaction split type. Returns False if not found or not owned."""
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
        )
    )
    txn = result.scalar_one_or_none()
    if not txn:
        return False

    # split_type lives on TransactionSplit, not Transaction — upsert the row
    split_result = await db.execute(
        select(TransactionSplit).where(TransactionSplit.transaction_id == transaction_id)
    )
    split = split_result.scalar_one_or_none()
    if split:
        split.split_type = split_type
        split.decided_by_user_id = user_id
        split.decided_at = datetime.now(timezone.utc)
    else:
        db.add(
            TransactionSplit(
                transaction_id=transaction_id,
                split_type=split_type,
                decided_by_user_id=user_id,
                decided_at=datetime.now(timezone.utc),
            )
        )
    await db.commit()
    return True


async def get_pending_transactions(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """
    Return pending transactions grouped into 3 buckets:
    - awaiting_reconciliation: email/plaid txns still in 'pending' status
    - needs_classification: connect txns, settled, no category yet
    - unmatched_email: email txns aged out to 'orphan' (migration 039, Task 2.8)
    """
    # All pending transactions (email + plaid processing). Exclude rows that
    # already participate in a transfer or refund pair — the pair is already
    # resolved conceptually; showing both legs in Pendientes is noise.
    email_pending_result = await db.execute(
        select(Transaction, TransactionSplit, BankAccount.bank_name)
        .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
        .where(
            Transaction.user_id == user_id,
            Transaction.source.in_(["gmail", "outlook", "plaid"]),
            Transaction.status == "pending",
            Transaction.transfer_pair_id.is_(None),
            Transaction.refund_pair_id.is_(None),
        )
        .order_by(Transaction.transaction_date.desc())
    )
    email_pending_rows = email_pending_result.all()

    # Connect transactions needing classification (exclude paired rows — a
    # transfer leg doesn't need a category, a refund pair nets to zero).
    needs_class_result = await db.execute(
        select(Transaction, TransactionSplit, BankAccount.bank_name)
        .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
        .where(
            Transaction.user_id == user_id,
            Transaction.source == "connect",
            Transaction.status == "settled",
            Transaction.category.is_(None),
            Transaction.transfer_pair_id.is_(None),
            Transaction.refund_pair_id.is_(None),
        )
        .order_by(Transaction.transaction_date.desc())
    )
    needs_class_rows = needs_class_result.all()

    # Orphaned email transactions (aged out without a Plaid match)
    orphan_result = await db.execute(
        select(Transaction, TransactionSplit, BankAccount.bank_name)
        .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
        .where(
            Transaction.user_id == user_id,
            Transaction.source_type == "email",
            Transaction.status == "orphan",
        )
        .order_by(Transaction.orphaned_at.desc().nullslast())
    )
    orphan_rows = orphan_result.all()

    def _pending_to_dict(txn, split, bank_name):
        d = _txn_to_dict(txn, split)
        d["bank_name"] = bank_name or txn.source_bank_name
        return d

    awaiting = [_pending_to_dict(txn, split, bn) for txn, split, bn in email_pending_rows]
    needs_classification = [_pending_to_dict(txn, split, bn) for txn, split, bn in needs_class_rows]
    unmatched_email = [_pending_to_dict(txn, split, bn) for txn, split, bn in orphan_rows]

    return {
        "awaiting_reconciliation": awaiting,
        "needs_classification": needs_classification,
        "unmatched_email": unmatched_email,
    }


async def delete_transaction(
    db: AsyncSession, transaction_id: uuid.UUID, user_id: uuid.UUID
) -> str:
    """
    Hard delete a pending or orphan email transaction.
    Returns: 'deleted', 'not_found', or 'invalid'.
    """
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
        )
    )
    txn = result.scalar_one_or_none()
    if not txn:
        return "not_found"
    if txn.source_type != "email" or txn.status not in ("pending", "orphan"):
        return "invalid"
    # Delete associated splits first to avoid FK violation
    await db.execute(
        sql_delete(TransactionSplit).where(TransactionSplit.transaction_id == transaction_id)
    )
    await db.delete(txn)
    await db.commit()
    return "deleted"


async def is_duplicate_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    amount: int,
    bank_name: str | None = None,
    currency: str | None = None,
) -> bool:
    """
    Two-tier dedup for email transactions:
    1. Same amount + SAME currency + SAME bank within 5 min → duplicate (BChile compra+comprobante)
    2. Same amount + SAME currency + DIFFERENT bank within 24h → duplicate (BofA + PayPal for same charge)

    Tier 1 catches fast duplicates from the same sender.
    Tier 2 catches slow cross-sender duplicates (e.g. PayPal alert hours after BofA alert).
    Currency + bank scoping prevents cross-currency / cross-bank false positives
    (e.g. CLP 2000 and USD 2000 arriving seconds apart are not duplicates).
    Neither blocks legitimate repeat purchases (3 beers at $7 from the same bank).
    """
    now = datetime.now(timezone.utc)

    # Tier 1: same bank, same currency, 5-min window (BChile compra + comprobante)
    fast_cutoff = now - timedelta(minutes=5)
    fast_conds = [
        Transaction.user_id == user_id,
        func.abs(Transaction.amount) == abs(amount),
        Transaction.status == "pending",
        Transaction.created_at >= fast_cutoff,
    ]
    if currency is not None:
        fast_conds.append(Transaction.currency == currency)
    if bank_name is not None:
        fast_conds.append(Transaction.source_bank_name == bank_name)
    fast_result = await db.execute(select(Transaction).where(*fast_conds).limit(1))
    if fast_result.scalar_one_or_none():
        return True

    # Tier 2: different bank, same currency, 5min–24h window
    # (BofA alert followed by a PayPal alert hours later for the same charge).
    # We explicitly exclude the ≤5 min window so two legitimate, unrelated
    # same-amount charges from different banks at roughly the same time
    # are not silently dropped.
    if bank_name:
        slow_cutoff = now - timedelta(hours=24)
        slow_conds = [
            Transaction.user_id == user_id,
            func.abs(Transaction.amount) == abs(amount),
            Transaction.status == "pending",
            Transaction.created_at >= slow_cutoff,
            Transaction.created_at < fast_cutoff,
            Transaction.source_bank_name != bank_name,
        ]
        if currency is not None:
            slow_conds.append(Transaction.currency == currency)
        slow_result = await db.execute(select(Transaction).where(*slow_conds).limit(1))
        if slow_result.scalar_one_or_none():
            return True

    return False


def exclude_from_totals(query):
    """Apply the invariant that transfers, refund pairs, and orphans do not
    contribute to spend/income/budget totals.

    Use this helper whenever aggregating (SUM) over `transactions`. Do NOT use
    it to filter list views — paired rows should remain visible and the
    frontend groups them visually.
    """
    return query.where(
        Transaction.status != "orphan",
        Transaction.transfer_pair_id.is_(None),
        Transaction.refund_pair_id.is_(None),
    )


class ServiceError(Exception):
    """Sentinel for service-layer authorization / state errors.

    `code` maps 1:1 onto an HTTP status in the router (403/404/409/422).
    """

    def __init__(self, code: str, message: str = ""):
        self.code = code
        super().__init__(message or code)


async def get_match_candidates(
    db: AsyncSession,
    user_id: uuid.UUID,
    pending_id: uuid.UUID,
    window_days: int = 7,
    limit: int = 20,
) -> list[dict]:
    """Return ranked candidate Plaid bank rows that could match a pending email row.

    Authorization: pending row must be owned by `user_id`. Candidates are
    filtered by household membership, same currency, 2% amount tolerance,
    ±window_days, unpaired, settled. Raises ServiceError('not_found') if the
    pending row doesn't exist or isn't owned by the caller.
    """
    # Load & authorize the pending email row (ownership enforced in SQL).
    pending_result = await db.execute(
        select(Transaction).where(
            Transaction.id == pending_id,
            Transaction.user_id == user_id,
        )
    )
    pending = pending_result.scalar_one_or_none()
    if not pending:
        raise ServiceError("not_found", "Pending transaction not found")

    # Verify the caller is a member of the pending row's household.
    member_result = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.household_id == pending.household_id,
            HouseholdMember.user_id == user_id,
            HouseholdMember.left_at.is_(None),
        )
    )
    if not member_result.scalar_one_or_none():
        raise ServiceError("not_found", "Pending transaction not found")

    pending_amount = Decimal(str(pending.amount))
    pending_abs = abs(pending_amount)
    tolerance = pending_abs * Decimal("0.02")
    date_min = pending.transaction_date - timedelta(days=window_days)
    date_max = pending.transaction_date + timedelta(days=window_days)

    result = await db.execute(
        select(Transaction, BankAccount.bank_name, BankAccount.account_name)
        .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
        .where(
            Transaction.household_id == pending.household_id,
            Transaction.currency == pending.currency,
            Transaction.source == "plaid",
            Transaction.status == "settled",
            Transaction.transfer_pair_id.is_(None),
            Transaction.refund_pair_id.is_(None),
            Transaction.transaction_date >= date_min,
            Transaction.transaction_date <= date_max,
            func.abs(Transaction.amount - pending_amount) <= tolerance,
        )
    )
    rows = result.all()

    def _rank(row):
        txn = row[0]
        date_delta = abs((txn.transaction_date - pending.transaction_date).total_seconds())
        amount_delta = abs(Decimal(str(txn.amount)) - pending_amount)
        return (date_delta, amount_delta)

    ranked = sorted(rows, key=_rank)[:limit]

    return [
        {
            "id": txn.id,
            "bank_account_id": txn.bank_account_id,
            "bank_account_name": account_name or bank_name,
            "transaction_date": txn.transaction_date,
            "amount": txn.amount,
            "currency": txn.currency,
            "raw_merchant_name": txn.raw_merchant_name,
            "category": txn.category,
        }
        for txn, bank_name, account_name in ranked
    ]


async def link_email_to_bank(
    db: AsyncSession,
    user_id: uuid.UUID,
    pending_id: uuid.UUID,
    bank_tx_id: uuid.UUID,
) -> dict:
    """Manually link a pending email row to a settled bank row.

    Enforces user_id ownership on BOTH rows in SQL. Returns the enriched bank
    transaction as a dict. Raises ServiceError with code:
      - 'not_found'     — either row is missing
      - 'forbidden'     — either row is owned by a different user
      - 'conflict'      — bank row already paired (transfer_pair_id or refund_pair_id)
    """
    from modules.reconciliation.dedup import apply_match_and_delete_emails, _extract_enrichment

    # Atomically load both rows and check ownership in the same SQL call.
    result = await db.execute(
        select(Transaction).where(Transaction.id.in_([pending_id, bank_tx_id]))
    )
    rows = {r.id: r for r in result.scalars().all()}
    pending = rows.get(pending_id)
    bank = rows.get(bank_tx_id)
    if not pending or not bank:
        raise ServiceError("not_found", "Transaction not found")
    if pending.user_id != user_id or bank.user_id != user_id:
        raise ServiceError("forbidden", "Not owner of transaction")
    if bank.transfer_pair_id is not None or bank.refund_pair_id is not None:
        raise ServiceError("conflict", "Bank transaction already paired")

    enrichment = await _extract_enrichment(db, pending.id)
    await apply_match_and_delete_emails(
        db,
        bank_tx_id=bank.id,
        email_tx_ids=[pending.id],
        enrichment=enrichment,
        user_id=user_id,
    )

    # When the user vincula a transfer-typed pending, try to auto-pair the
    # newly-typed bank tx with its twin on another account (e.g., AmEx payment
    # email linked to BofA's outgoing leg should ALSO rope in the AmEx card's
    # incoming leg). Targeted to this one tx to avoid re-pairing unrelated rows.
    if enrichment.get("transaction_type") == "transfer":
        from modules.reconciliation.transfers import pair_transfer_twin

        await pair_transfer_twin(db, bank.id)

    await db.commit()

    # Reload the bank tx with enrichment applied.
    refreshed = await db.execute(
        select(Transaction, TransactionSplit, BankAccount.bank_name)
        .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
        .where(Transaction.id == bank.id)
    )
    row = refreshed.one_or_none()
    if not row:
        raise ServiceError("not_found", "Bank transaction vanished after link")
    txn, split, bank_name = row
    return {
        **{k: v for k, v in vars(txn).items() if not k.startswith("_")},
        "split_type": split.split_type if split else None,
        "bank_name": bank_name or txn.source_bank_name,
        "account_kind": None,
        "display_name": None,
    }


async def dismiss_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    transaction_id: uuid.UUID,
) -> None:
    """Mark a pending transaction as orphan (user-dismissed).

    Enforces user_id ownership in SQL. Raises ServiceError with code:
      - 'not_found' — row missing
      - 'forbidden' — row owned by another user
      - 'conflict'  — row is already orphan or not in 'pending' status
    """
    result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    txn = result.scalar_one_or_none()
    if not txn:
        raise ServiceError("not_found", "Transaction not found")
    if txn.user_id != user_id:
        raise ServiceError("forbidden", "Not owner of transaction")
    if txn.status == "orphan":
        raise ServiceError("conflict", "Transaction already dismissed")
    if txn.status != "pending":
        raise ServiceError("conflict", "Only pending transactions can be dismissed")

    await db.execute(
        sql_update(Transaction)
        .where(Transaction.id == transaction_id, Transaction.user_id == user_id)
        .values(
            status="orphan",
            orphaned_at=datetime.now(timezone.utc),
            dismissed_by_user=True,
        )
    )
    await db.commit()


async def bulk_action(
    db: AsyncSession,
    user_id: uuid.UUID,
    transaction_ids: list[uuid.UUID],
    action: str,
) -> int:
    """Bulk 'dismiss' or 'delete' a set of caller-owned transactions.

    All-or-nothing: if ANY id is missing or owned by a different user, raises
    ServiceError('forbidden') and performs NO side effects. Caps at 100 ids —
    raises ServiceError('too_many') above that.
    """
    if action not in ("dismiss", "delete"):
        raise ServiceError("invalid_action", "action must be 'dismiss' or 'delete'")
    if len(transaction_ids) == 0:
        return 0
    if len(transaction_ids) > 100:
        raise ServiceError("too_many", "Maximum 100 ids per bulk action")

    # Ownership check in a single SQL call.
    owned_result = await db.execute(
        select(Transaction.id).where(
            Transaction.id.in_(transaction_ids),
            Transaction.user_id == user_id,
        )
    )
    owned_ids = {row[0] for row in owned_result.all()}
    if len(owned_ids) != len(set(transaction_ids)):
        raise ServiceError("forbidden", "One or more transactions not owned by caller")

    if action == "dismiss":
        await db.execute(
            sql_update(Transaction)
            .where(
                Transaction.id.in_(transaction_ids),
                Transaction.user_id == user_id,
            )
            .values(
                status="orphan",
                orphaned_at=datetime.now(timezone.utc),
                dismissed_by_user=True,
            )
        )
    else:  # delete
        # Clear child splits first to respect FK.
        await db.execute(
            sql_delete(TransactionSplit).where(TransactionSplit.transaction_id.in_(transaction_ids))
        )
        await db.execute(
            sql_delete(Transaction).where(
                Transaction.id.in_(transaction_ids),
                Transaction.user_id == user_id,
            )
        )
    await db.commit()
    return len(transaction_ids)


def _txn_to_dict(txn: Transaction, split: TransactionSplit | None) -> dict:
    """Convert Transaction + optional Split to response dict."""
    return {
        **{k: v for k, v in vars(txn).items() if not k.startswith("_")},
        "split_type": split.split_type if split else None,
        "bank_name": txn.source_bank_name,
        "account_kind": None,
        "display_name": None,
    }
