"""044 — add transactions.reimbursement_group_id

Revision ID: 044
Revises: 043

Adds a nullable UUID column + index to mark transactions that were grouped
manually as a reimbursement (e.g. school/work pays back N expenses with one
inflow). Rows sharing the same reimbursement_group_id are excluded from
spending totals so reporting nets to zero.

Distinct from transfer_pair_id (own-account moves, exactly 2 legs) and
refund_pair_id (auto-detected merchant refunds): reimbursement is a
user-driven semantic claim with N+1 cardinality.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision = "044"
down_revision = "043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("reimbursement_group_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_transactions_reimbursement_group",
        "transactions",
        ["reimbursement_group_id"],
        postgresql_where=sa.text("reimbursement_group_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_reimbursement_group", table_name="transactions")
    op.drop_column("transactions", "reimbursement_group_id")
