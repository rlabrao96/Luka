"""Add phone_whatsapp column to users table.

Revision ID: 013
Revises: 012
"""

import sqlalchemy as sa
from alembic import op

revision = "013"
down_revision = "012"


def upgrade() -> None:
    op.add_column("users", sa.Column("phone_whatsapp", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "phone_whatsapp")
