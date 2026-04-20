"""Indexes for hot auth and household-membership paths.

Every authenticated request runs through get_current_user → /auth/me →
require_membership, all of which query household_members by user_id / household_id.
On Supabase the table sits behind RLS so we need real btree indexes to avoid
sequential scans. household_invites lookups by token are already unique-indexed,
but we also want a partial index on pending invites by (household_id, invited_email)
for the revoke-prior-pending-invite path in create_invite.

Revision ID: 038
Revises: 037
Create Date: 2026-04-20
"""

from alembic import op


revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_household_members_user_active "
        "ON household_members (user_id) WHERE left_at IS NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_household_members_household_active "
        "ON household_members (household_id) WHERE left_at IS NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_household_invites_pending "
        "ON household_invites (household_id, LOWER(invited_email)) "
        "WHERE accepted_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_household_invites_pending")
    op.execute("DROP INDEX IF EXISTS ix_household_members_household_active")
    op.execute("DROP INDEX IF EXISTS ix_household_members_user_active")
