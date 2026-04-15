"""036 — add subscription_overrides.split_type

Revision ID: 036
Revises: 035
"""

import sqlalchemy as sa
from alembic import op

revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscription_overrides",
        sa.Column("split_type", sa.String(), nullable=True),
    )
    op.create_check_constraint(
        "ck_subscription_overrides_split_type",
        "subscription_overrides",
        "split_type IS NULL OR split_type IN ('personal', 'shared')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_subscription_overrides_split_type",
        "subscription_overrides",
        type_="check",
    )
    op.drop_column("subscription_overrides", "split_type")
