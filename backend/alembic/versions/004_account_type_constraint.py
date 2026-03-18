"""Enforce account_type IN ('personal', 'partner', 'joint').

Revision ID: 004
Down revision: 003
"""

from alembic import op

revision = "004"
down_revision = "003"


def upgrade():
    # Existing rows only have 'personal' or 'joint' — both valid under new constraint.
    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE bank_accounts ADD CONSTRAINT chk_bank_account_type
                CHECK (account_type IN ('personal', 'partner', 'joint'));
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END
        $$;
        """
    )


def downgrade():
    op.execute("ALTER TABLE bank_accounts " "DROP CONSTRAINT IF EXISTS chk_bank_account_type")
