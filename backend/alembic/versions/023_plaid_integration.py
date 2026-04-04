"""plaid_integration

Revision ID: 023
Revises: 022
Create Date: 2026-04-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create plaid_items table
    op.create_table(
        "plaid_items",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "household_id",
            UUID(as_uuid=True),
            sa.ForeignKey("households.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plaid_item_id", sa.String, nullable=False, unique=True),
        sa.Column("access_token", sa.String, nullable=False),
        sa.Column("institution_id", sa.String, nullable=False),
        sa.Column("institution_name", sa.String, nullable=False),
        sa.Column("cursor", sa.Text, nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_status", sa.String, nullable=True),
        sa.Column("error_code", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # 2. Add columns to bank_accounts
    op.add_column(
        "bank_accounts",
        sa.Column("provider", sa.String, server_default="luka_connect", nullable=False),
    )
    op.add_column(
        "bank_accounts", sa.Column("country", sa.String(2), server_default="CL", nullable=False)
    )
    op.add_column(
        "bank_accounts",
        sa.Column(
            "plaid_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("plaid_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("bank_accounts", sa.Column("plaid_account_id", sa.String, nullable=True))

    # 3. Add columns to transactions
    op.add_column("transactions", sa.Column("transfer_pair_id", UUID(as_uuid=True), nullable=True))
    op.add_column("transactions", sa.Column("plaid_transaction_id", sa.String, nullable=True))

    # 4. Partial unique index on plaid_transaction_id
    op.create_index(
        "ix_transactions_plaid_transaction_id",
        "transactions",
        ["plaid_transaction_id"],
        unique=True,
        postgresql_where=sa.text("plaid_transaction_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_plaid_transaction_id", table_name="transactions")
    op.drop_column("transactions", "plaid_transaction_id")
    op.drop_column("transactions", "transfer_pair_id")
    op.drop_column("bank_accounts", "plaid_account_id")
    op.drop_column("bank_accounts", "plaid_item_id")
    op.drop_column("bank_accounts", "country")
    op.drop_column("bank_accounts", "provider")
    op.drop_table("plaid_items")
