"""Add category_budgets table

Revision ID: 029
Revises: 028
Create Date: 2026-04-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "category_budgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name="fk_category_budgets_household_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "household_id",
            "category",
            "month",
            name="uq_category_budgets_household_cat_month",
        ),
    )


def downgrade() -> None:
    op.drop_table("category_budgets")
