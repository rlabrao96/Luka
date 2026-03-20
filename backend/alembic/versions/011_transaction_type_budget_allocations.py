"""transaction_type and household_budget_allocations

Revision ID: 011
Revises: 010
Create Date: 2026-03-20
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "011"
down_revision: Union[str, Sequence[str], None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add transaction_type to transactions
    op.add_column(
        "transactions",
        sa.Column(
            "transaction_type",
            sa.String(10),
            nullable=False,
            server_default="expense",
        ),
    )
    op.create_check_constraint(
        "ck_transaction_type",
        "transactions",
        "transaction_type IN ('expense', 'income', 'transfer')",
    )

    # 2. Add transfer_to_account_id to transactions
    op.add_column(
        "transactions",
        sa.Column(
            "transfer_to_account_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_transactions_transfer_to_account",
        "transactions",
        "bank_accounts",
        ["transfer_to_account_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 3. Create household_budget_allocations table
    op.create_table(
        "household_budget_allocations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("hogar_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("ahorro_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("personal_pct", sa.Numeric(5, 2), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("household_id", "month", name="uq_budget_allocation_household_month"),
        sa.CheckConstraint("hogar_pct + ahorro_pct + personal_pct = 100", name="ck_pct_sum"),
    )


def downgrade() -> None:
    op.drop_table("household_budget_allocations")
    op.drop_constraint("fk_transactions_transfer_to_account", "transactions", type_="foreignkey")
    op.drop_column("transactions", "transfer_to_account_id")
    op.drop_constraint("ck_transaction_type", "transactions", type_="check")
    op.drop_column("transactions", "transaction_type")
