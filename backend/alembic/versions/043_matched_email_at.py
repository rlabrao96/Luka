"""043 — add transactions.matched_email_at

Revision ID: 043
Revises: 042

Idempotency marker for the email-vs-bank matcher: when an email transaction
is consolidated onto a Plaid/bank row, we stamp `matched_email_at`. Future
reconciliation passes exclude rows where this is non-null so the same Plaid
row can never be claimed twice.
"""

import sqlalchemy as sa
from alembic import op


revision = "043"
down_revision = "042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("matched_email_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transactions", "matched_email_at")
