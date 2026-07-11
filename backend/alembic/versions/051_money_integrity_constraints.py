"""051 — money-integrity constraints and hot-path indexes

Revision ID: 051
Revises: 050

Every budget / summary / settlement aggregate JOINs transaction_splits, so a
transaction with two split rows is silently double-counted in money totals.
The Plaid pending→settled swap could produce exactly that (the replacement
got a default split in the added path AND inherited the old txn's split in
the removed path). The code path is fixed; this migration:

1. Deduplicates existing transaction_splits (keeps the row carrying user
   intent — decided_at set, else newest created_at).
2. Adds a UNIQUE index on transaction_splits.transaction_id so this class of
   bug becomes a loud constraint violation instead of silent double money,
   and drops the now-redundant plain index.
3. Adds the missing (user_id, transaction_date) composite index — every hot
   dashboard / reconciliation query filters by owner + date range.
   (household_id, transaction_date) already exists from migration 039;
   the (trip_expense_id, attendee_id) unique already exists from 046.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "051"
down_revision: Union[str, Sequence[str], None] = "050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Dedup: keep, per transaction, the split with decided_at set (user
    #    intent) first, newest created_at second; delete the rest.
    op.execute(
        """
        DELETE FROM transaction_splits ts
        USING (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY transaction_id
                       ORDER BY (decided_at IS NOT NULL) DESC,
                                created_at DESC,
                                id
                   ) AS rn
            FROM transaction_splits
        ) ranked
        WHERE ts.id = ranked.id AND ranked.rn > 1
        """
    )

    # 2. One split row per transaction — ever.
    op.create_index(
        "uq_transaction_splits_transaction_id",
        "transaction_splits",
        ["transaction_id"],
        unique=True,
    )
    op.execute("DROP INDEX IF EXISTS ix_transaction_splits_transaction_id")

    # 3. Composite hot-path index (user_id + date range + date sort).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_transactions_user_date "
        "ON transactions (user_id, transaction_date)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_transactions_user_date")
    op.create_index(
        "ix_transaction_splits_transaction_id",
        "transaction_splits",
        ["transaction_id"],
    )
    op.drop_index("uq_transaction_splits_transaction_id", table_name="transaction_splits")
