"""Add encrypted Google OAuth token columns to users.

Revision ID: 016
Revises: 015
"""

import sqlalchemy as sa
from alembic import op

revision = "016"
down_revision = "015"


def upgrade() -> None:
    op.add_column("users", sa.Column("google_access_token_enc", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("google_refresh_token_enc", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "google_refresh_token_enc")
    op.drop_column("users", "google_access_token_enc")
