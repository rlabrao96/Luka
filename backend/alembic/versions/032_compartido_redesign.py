"""Compartido redesign: settlement_enabled, left_at, nullable invited_email, couple->group migration

Revision ID: 032
Revises: 031
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add settlement_enabled to households
    op.add_column(
        "households",
        sa.Column(
            "settlement_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
    )

    # 2. Add left_at to household_members
    op.add_column(
        "household_members",
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 3. Make invited_email nullable on household_invites
    op.alter_column("household_invites", "invited_email", existing_type=sa.String(), nullable=True)

    # 4. Migrate couple -> group
    op.execute("UPDATE households SET type = 'group' WHERE type = 'couple'")

    # 5. Migrate partner split type -> compartido (if any remain)
    op.execute(
        "UPDATE transaction_splits SET split_type = 'compartido' WHERE split_type = 'partner'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE transaction_splits SET split_type = 'partner' WHERE split_type = 'compartido'"
    )
    op.execute("UPDATE households SET type = 'couple' WHERE type = 'group'")
    op.alter_column("household_invites", "invited_email", existing_type=sa.String(), nullable=False)
    op.drop_column("household_members", "left_at")
    op.drop_column("households", "settlement_enabled")
