"""Add account_kind column to bank_accounts.

Revision ID: 006
Down revision: 005
"""

import sqlalchemy as sa
from alembic import op

revision = "006"
down_revision = "005"


def upgrade():
    op.add_column(
        "bank_accounts",
        sa.Column(
            "account_kind",
            sa.String(),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("bank_accounts", "account_kind")
