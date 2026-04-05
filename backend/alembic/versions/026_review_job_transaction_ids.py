"""add transaction_ids JSONB column to merchant_review_jobs

Revision ID: 026
Revises: 025
Create Date: 2026-04-04
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("merchant_review_jobs", sa.Column("transaction_ids", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("merchant_review_jobs", "transaction_ids")
