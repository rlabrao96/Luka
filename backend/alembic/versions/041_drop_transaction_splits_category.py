"""041 — drop transaction_splits.category

Revision ID: 041
Revises: 040

`transactions.category` is the canonical category field. The duplicate
column on `transaction_splits` was historical drift — only the WhatsApp
handler ever wrote to it, only `get_category_usage` ever read it, and the
two diverged whenever a user categorized via the web UI (which only
updated `transactions.category`). That mismatch silently broke the
category-delete reclassify flow.

Before dropping, copy any orphan WhatsApp-only split categories back to
the transaction row so no information is lost.
"""

import sqlalchemy as sa
from alembic import op

revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE transactions t
        SET category = ts.category
        FROM transaction_splits ts
        WHERE ts.transaction_id = t.id
          AND t.category IS NULL
          AND ts.category IS NOT NULL
        """
    )
    op.drop_column("transaction_splits", "category")


def downgrade() -> None:
    op.add_column(
        "transaction_splits",
        sa.Column("category", sa.String(), nullable=True),
    )
