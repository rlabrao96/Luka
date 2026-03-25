import uuid
from datetime import date, datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func, delete as sql_delete
from modules.transactions.models import Transaction, TransactionSplit
from modules.households.models import BankAccount


async def get_my_transactions(db: AsyncSession, user_id: uuid.UUID, since: date) -> list[dict]:
    result = await db.execute(
        select(Transaction, TransactionSplit, BankAccount.bank_name, BankAccount.account_kind)
        .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
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
            "bank_name": bank_name,
            "account_kind": account_kind,
        }
        for txn, split, bank_name, account_kind in rows
    ]


async def get_monthly_summary(
    db: AsyncSession, household_id: uuid.UUID, user_id: uuid.UUID
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
    result = await db.execute(
        text("""
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
        {"household_id": str(household_id), "user_id": str(user_id)},
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
        select(Transaction, TransactionSplit, BankAccount.bank_name)
        .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
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
            "bank_name": bank_name,
        }
        for txn, split, bank_name in rows
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
    txn.split_type = split_type
    await db.commit()
    return True


async def get_pending_transactions(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """
    Return pending transactions grouped into 3 buckets:
    - awaiting_reconciliation: email txns, pending, no sync has run since creation
    - needs_classification: Fintoc txns, settled, no category
    - unmatched_email: email txns, pending, at least 1 sync ran since creation
    """
    # All pending email transactions
    email_pending_result = await db.execute(
        select(Transaction, TransactionSplit)
        .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .where(
            Transaction.user_id == user_id,
            Transaction.source.in_(["gmail", "outlook"]),
            Transaction.status == "pending",
        )
        .order_by(Transaction.transaction_date.desc())
    )
    email_pending_rows = email_pending_result.all()

    # Fintoc transactions needing classification
    needs_class_result = await db.execute(
        select(Transaction, TransactionSplit)
        .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .where(
            Transaction.user_id == user_id,
            Transaction.source == "fintoc",
            Transaction.status == "settled",
            Transaction.category.is_(None),
        )
        .order_by(Transaction.transaction_date.desc())
    )
    needs_class_rows = needs_class_result.all()

    # Get max_synced_at value
    synced_result = await db.execute(
        select(func.max(BankAccount.last_synced_at)).where(
            BankAccount.user_id == user_id, BankAccount.is_active.is_(True)
        )
    )
    max_synced_at = synced_result.scalar_one_or_none()

    # Split email pending into awaiting vs unmatched
    awaiting = []
    unmatched = []
    for txn, split in email_pending_rows:
        row = _txn_to_dict(txn, split)
        if max_synced_at is None or max_synced_at < txn.created_at:
            awaiting.append(row)
        else:
            unmatched.append(row)

    needs_classification = [_txn_to_dict(txn, split) for txn, split in needs_class_rows]

    return {
        "awaiting_reconciliation": awaiting,
        "needs_classification": needs_classification,
        "unmatched_email": unmatched,
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


async def is_duplicate_transaction(db: AsyncSession, user_id: uuid.UUID, amount: int) -> bool:
    """
    Check if a pending transaction with the same amount was created in the last 5 minutes.
    Used to deduplicate Banco de Chile compra + comprobante email pairs.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    result = await db.execute(
        select(Transaction)
        .where(
            Transaction.user_id == user_id,
            Transaction.amount == amount,
            Transaction.status == "pending",
            Transaction.created_at >= cutoff,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


def _txn_to_dict(txn: Transaction, split: TransactionSplit | None) -> dict:
    """Convert Transaction + optional Split to response dict."""
    return {
        **{k: v for k, v in vars(txn).items() if not k.startswith("_")},
        "split_type": split.split_type if split else None,
        "bank_name": None,
        "account_kind": None,
    }
