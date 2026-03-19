"""Add account_number column to bank_accounts.

Revision ID: 007
Down revision: 006
"""

import sqlalchemy as sa
from alembic import op

revision = "007"
down_revision = "006"


def upgrade():
    op.add_column(
        "bank_accounts",
        sa.Column("account_number", sa.String(), nullable=True),
    )


def downgrade():
    op.drop_column("bank_accounts", "account_number")
