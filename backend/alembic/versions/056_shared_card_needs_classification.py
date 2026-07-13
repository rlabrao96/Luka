"""056 — transactions.needs_classification (shared-card charge sort)

Revision ID: 056
Revises: 055
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "056"
down_revision: Union[str, Sequence[str], None] = "055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "needs_classification", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.create_index(
        "ix_transactions_needs_classification",
        "transactions",
        ["needs_classification"],
        postgresql_where=sa.text("needs_classification"),
    )
    # Widen the account_type enum-by-constraint (migration 004) to admit the
    # new 'shared_card' value. Storage only — no logic reads it yet.
    op.execute("ALTER TABLE bank_accounts DROP CONSTRAINT IF EXISTS chk_bank_account_type")
    op.execute(
        """
        ALTER TABLE bank_accounts ADD CONSTRAINT chk_bank_account_type
            CHECK (account_type IN ('personal', 'partner', 'joint', 'shared_card'))
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE bank_accounts DROP CONSTRAINT IF EXISTS chk_bank_account_type")
    op.execute(
        """
        ALTER TABLE bank_accounts ADD CONSTRAINT chk_bank_account_type
            CHECK (account_type IN ('personal', 'partner', 'joint'))
        """
    )
    op.drop_index("ix_transactions_needs_classification", table_name="transactions")
    op.drop_column("transactions", "needs_classification")
