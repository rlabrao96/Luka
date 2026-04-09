"""Enforce at most one active household membership per user

Context: A manual SQL UPDATE on 2026-04-08 set `left_at` on two users'
individual-household rows in one statement; one of them (Juan José Buenahora)
was left orphaned with zero active memberships, causing his next login to
redirect to /onboarding instead of the dashboard because `/auth/me` returned
`household_id=null`.

This migration adds a partial unique index on `household_members(user_id)`
filtered by `left_at IS NULL`, enforcing the business rule already present
in `accept_invite` (service.py:77-96): a user can be in at most one active
household at a time. Orphans (zero active rows) can't be prevented at the DB
layer without a constraint trigger — but duplicate-active rows *can*, and
this closes the worse half of the corruption surface.

Revision ID: 034
Revises: 033
Create Date: 2026-04-09
"""

from alembic import op

revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
            uq_household_members_user_active
        ON household_members (user_id)
        WHERE left_at IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_household_members_user_active")
