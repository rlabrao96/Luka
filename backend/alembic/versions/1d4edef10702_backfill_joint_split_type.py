"""backfill joint split type

Revision ID: 1d4edef10702
Revises: 041
Create Date: 2026-04-27 00:57:39.173081

Historical bug: the Plaid sync and bank_connect ingestion paths called
``ensure_default_split(db, txn)`` without ``default_split_type='shared'``,
so transactions on joint bank accounts were stored with
``split_type='personal'`` instead of ``'shared'``. Task 2 of the
merchant-card-classification-ux plan fixed the ingestion sites; this
migration corrects the historical rows.

Idempotent: re-running is safe because the WHERE clause filters
``split_type = 'personal'`` — already-corrected rows are skipped.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "1d4edef10702"
down_revision: Union[str, Sequence[str], None] = "041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Set split_type='shared' on every TransactionSplit whose underlying
    transaction belongs to a joint bank account, where it's currently
    'personal'."""
    op.execute("""
        UPDATE transaction_splits ts
        SET split_type = 'shared'
        FROM transactions t
        JOIN bank_accounts ba ON ba.id = t.bank_account_id
        WHERE ts.transaction_id = t.id
          AND ba.account_type = 'joint'
          AND ts.split_type = 'personal'
          AND t.transaction_type != 'transfer'
    """)
    # Note: transfers don't get TransactionSplit rows (ensure_default_split
    # skips them), so the transaction_type filter is belt-and-suspenders —
    # preserves the invariant if any historic transfer accidentally got a
    # split row.


def downgrade() -> None:
    """No-op: we cannot tell which rows were originally personal vs shared."""
    pass
