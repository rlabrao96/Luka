"""Add split_ratio JSONB column to households."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision = "019"
down_revision = "018"


def upgrade() -> None:
    op.add_column(
        "households",
        sa.Column("split_ratio", JSONB, server_default="[50, 50]", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("households", "split_ratio")
