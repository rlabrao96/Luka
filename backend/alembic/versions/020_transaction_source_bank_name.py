"""Add source_bank_name to transactions for email-inferred bank identification."""

import sqlalchemy as sa
from alembic import op

revision = "020"
down_revision = "019"


def upgrade() -> None:
    op.add_column("transactions", sa.Column("source_bank_name", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("transactions", "source_bank_name")
