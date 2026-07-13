"""055 — users.transactions_since (initial-sync start-date cutoff)

Revision ID: 055
Revises: 054

Lets a user bound how far back a newly-connected bank backfills. Bulk-history
ingestion (Plaid cursor sync, Luka Connect scrape) skips transactions dated
before this. NULL = no cutoff (current behavior). Additive, nullable — safe.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "055"
down_revision: Union[str, Sequence[str], None] = "054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("transactions_since", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "transactions_since")
