"""Add fintoc_link_id and fintoc_account_id to bank_accounts.

Revision ID: 003
Down revision: 002
"""

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"


def upgrade():
    op.add_column("bank_accounts", sa.Column("fintoc_link_id", sa.String(), nullable=True))
    op.add_column("bank_accounts", sa.Column("fintoc_account_id", sa.String(), nullable=True))


def downgrade():
    op.drop_column("bank_accounts", "fintoc_account_id")
    op.drop_column("bank_accounts", "fintoc_link_id")
