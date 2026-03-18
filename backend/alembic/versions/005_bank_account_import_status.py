"""Add import_status column to bank_accounts.

Revision ID: 005
Down revision: 004
"""

import sqlalchemy as sa
from alembic import op

revision = "005"
down_revision = "004"


def upgrade():
    op.add_column(
        "bank_accounts",
        sa.Column(
            "import_status",
            sa.String(),
            nullable=False,
            server_default="done",
        ),
    )


def downgrade():
    op.drop_column("bank_accounts", "import_status")
