import uuid
from datetime import date, datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, text, delete as sql_delete
from modules.transactions.models import Transaction, TransactionSplit
from modules.households.models import BankAccount
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
            Transaction.status != "pending",
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
    # All pending transactions (email + plaid processing)
    email_pending_result = await db.execute(
        select(Transaction, TransactionSplit, BankAccount.bank_name)
        .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
        .where(
            Transaction.user_id == user_id,
            Transaction.source.in_(["gmail", "outlook", "plaid"]),
            Transaction.status == "pending",
        )
        .order_by(Transaction.transaction_date.desc())
    )
    email_pending_rows = email_pending_result.all()

    # Connect transactions needing classification
    needs_class_result = await db.execute(
        select(Transaction, TransactionSplit, BankAccount.bank_name)
        .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
        .where(
            Transaction.user_id == user_id,
            Transaction.source == "connect",
            Transaction.status == "settled",
            Transaction.category.is_(None),
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
    Hard delete a pending email transaction.
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
    if txn.source not in ("gmail", "outlook") or txn.status != "pending":
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


def _txn_to_dict(txn: Transaction, split: TransactionSplit | None) -> dict:
    """Convert Transaction + optional Split to response dict."""
    return {
        **{k: v for k, v in vars(txn).items() if not k.startswith("_")},
        "split_type": split.split_type if split else None,
        "bank_name": txn.source_bank_name,
        "account_kind": None,
        "display_name": None,
    }
