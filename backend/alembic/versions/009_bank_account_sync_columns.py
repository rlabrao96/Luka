"""bank_account_sync_columns

Revision ID: 009
Revises: 008
Create Date: 2026-03-19

Add last_synced_at and import_started_at to bank_accounts.
- last_synced_at: set only on successful sync completion
- import_started_at: set when import begins; used for stale guard (stuck-import detection)
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "009"
down_revision: Union[str, Sequence[str], None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bank_accounts",
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "bank_accounts",
        sa.Column("import_started_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bank_accounts", "import_started_at")
    op.drop_column("bank_accounts", "last_synced_at")
