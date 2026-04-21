"""user_currencies table

Revision ID: 029b
Revises: 029

Historically this file shared revision id "029" with 029_category_budgets.py,
which left alembic with an ambiguous head. Renamed to "029b" and chained
after "029" so the graph linearises cleanly. Made idempotent so it is safe
to re-run against databases where the table was already created under the
old (broken) setup.
"""

from alembic import op


revision = "029b"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_currencies (
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            currency_code CHAR(3) NOT NULL,
            is_primary BOOLEAN NOT NULL DEFAULT false,
            sort_order INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, currency_code)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_currencies_user_id " "ON user_currencies (user_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_user_currencies_user_id")
    op.execute("DROP TABLE IF EXISTS user_currencies")
