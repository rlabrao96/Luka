"""037 — add user_budget_settings.personal_allocation_amount / _currency

Revision ID: 037
Revises: 036
"""

import sqlalchemy as sa
from alembic import op

revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_budget_settings",
        sa.Column("personal_allocation_amount", sa.Numeric(14, 2), nullable=True),
    )
    op.add_column(
        "user_budget_settings",
        sa.Column("personal_allocation_currency", sa.String(length=3), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_budget_settings", "personal_allocation_currency")
    op.drop_column("user_budget_settings", "personal_allocation_amount")
