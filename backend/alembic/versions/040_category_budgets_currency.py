"""040 — add currency column to category_budgets

Revision ID: 040
Revises: 039

Lets a household set different caps per currency for the same category in
the same month (e.g. Alimentación $600k CLP AND $300 USD). Backfills
existing rows with the household's `preferred_currency`-equivalent —
we fall back to 'CLP' because that's what the legacy single-currency cap
logic assumed.
"""

import sqlalchemy as sa
from alembic import op

revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "category_budgets",
        sa.Column("currency", sa.String(length=3), nullable=True),
    )
    op.execute("UPDATE category_budgets SET currency = 'CLP' WHERE currency IS NULL")
    op.alter_column("category_budgets", "currency", nullable=False)

    op.drop_constraint(
        "uq_category_budgets_household_cat_month",
        "category_budgets",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_category_budgets_household_cat_month_ccy",
        "category_budgets",
        ["household_id", "category", "month", "currency"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_category_budgets_household_cat_month_ccy",
        "category_budgets",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_category_budgets_household_cat_month",
        "category_budgets",
        ["household_id", "category", "month"],
    )
    op.drop_column("category_budgets", "currency")
