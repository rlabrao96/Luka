"""Add account_name, balance columns, and last_synced_at to bank_accounts."""

import sqlalchemy as sa
from alembic import op

revision = "018"
down_revision = "017"


def upgrade() -> None:
    op.add_column("bank_accounts", sa.Column("account_name", sa.String(), nullable=True))
    op.add_column("bank_accounts", sa.Column("balance_current", sa.BigInteger(), nullable=True))
    op.add_column("bank_accounts", sa.Column("balance_limit", sa.BigInteger(), nullable=True))
    op.add_column(
        "bank_accounts",
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bank_accounts", "last_synced_at")
    op.drop_column("bank_accounts", "balance_limit")
    op.drop_column("bank_accounts", "balance_current")
    op.drop_column("bank_accounts", "account_name")
