import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from modules.transactions.models import Transaction, TransactionSplit
from modules.households.models import BankAccount


async def get_my_transactions(db: AsyncSession, user_id: uuid.UUID, since: date) -> list[dict]:
    result = await db.execute(
        select(Transaction, TransactionSplit, BankAccount.bank_name, BankAccount.account_kind)
        .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .join(BankAccount, BankAccount.id == Transaction.bank_account_id)
        .where(
            Transaction.user_id == user_id,
            Transaction.transaction_date >= since,
            BankAccount.is_active.is_(True),
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
        .join(BankAccount, BankAccount.id == Transaction.bank_account_id)
        .where(
            Transaction.household_id == household_id,
            TransactionSplit.split_type == "shared",
            Transaction.transaction_date >= since,
            BankAccount.is_active.is_(True),
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
