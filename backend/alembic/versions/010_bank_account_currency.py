"""bank_account_currency

Revision ID: 010
Revises: 009
Create Date: 2026-03-20

Add currency column to bank_accounts.
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "010"
down_revision: Union[str, Sequence[str], None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bank_accounts",
        sa.Column("currency", sa.String(3), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bank_accounts", "currency")
