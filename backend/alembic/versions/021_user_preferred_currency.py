"""Add preferred_currency to users table."""

import sqlalchemy as sa
from alembic import op

revision = "021"
down_revision = "020"


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("preferred_currency", sa.String(), server_default="CLP", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "preferred_currency")
