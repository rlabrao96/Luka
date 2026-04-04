"""make merchant_review_jobs.bank_credential_id nullable for Plaid

Revision ID: 024
Revises: 023
Create Date: 2026-04-04
"""

from alembic import op
import sqlalchemy as sa

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "merchant_review_jobs",
        "bank_credential_id",
        existing_type=sa.dialects.postgresql.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "merchant_review_jobs",
        "bank_credential_id",
        existing_type=sa.dialects.postgresql.UUID(),
        nullable=False,
    )
