"""add balance columns to bank_accounts

Revision ID: 012
Revises: 011
Create Date: 2026-03-20
"""

from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: Union[str, Sequence[str], None] = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bank_accounts", sa.Column("balance_available", sa.BigInteger(), nullable=True))
    op.add_column("bank_accounts", sa.Column("balance_current", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("bank_accounts", "balance_current")
    op.drop_column("bank_accounts", "balance_available")
