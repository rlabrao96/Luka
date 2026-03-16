import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from modules.transactions.models import Transaction, TransactionSplit


async def get_my_transactions(db: AsyncSession, user_id: uuid.UUID, limit: int = 50) -> list[dict]:
    result = await db.execute(
        select(Transaction, TransactionSplit)
        .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.transaction_date.desc())
        .limit(limit)
    )
    rows = result.all()
    return [
        {
            **{k: v for k, v in vars(txn).items() if not k.startswith("_")},
            "split_type": split.split_type if split else None,
        }
        for txn, split in rows
    ]


async def get_shared_transactions(
    db: AsyncSession, household_id: uuid.UUID, limit: int = 50
) -> list[dict]:
    result = await db.execute(
        select(Transaction, TransactionSplit)
        .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .where(
            Transaction.household_id == household_id,
            TransactionSplit.split_type == "shared",
        )
        .order_by(Transaction.transaction_date.desc())
        .limit(limit)
    )
    rows = result.all()
    return [
        {
            **{k: v for k, v in vars(txn).items() if not k.startswith("_")},
            "split_type": split.split_type,
        }
        for txn, split in rows
    ]
