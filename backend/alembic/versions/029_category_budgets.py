"""Add category_budgets table

Revision ID: 029
Revises: 028
Create Date: 2026-04-05

Made idempotent (CREATE ... IF NOT EXISTS) because the revision id "029" was
historically shared with user_currencies; databases may have applied either
or both out of band before the graph was linearised.
"""

from alembic import op


revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS category_budgets (
            id UUID PRIMARY KEY,
            household_id UUID NOT NULL,
            category VARCHAR NOT NULL,
            month DATE NOT NULL,
            amount NUMERIC(12, 2) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT fk_category_budgets_household_id
                FOREIGN KEY (household_id) REFERENCES households(id) ON DELETE CASCADE,
            CONSTRAINT uq_category_budgets_household_cat_month
                UNIQUE (household_id, category, month)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS category_budgets")
