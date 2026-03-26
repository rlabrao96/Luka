"""Remove Fintoc columns, add bank_credentials table and source_type.

Revision ID: 017
Revises: 016
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision = "017"
down_revision = "016"


def upgrade() -> None:
    # --- Drop Fintoc columns from bank_accounts ---
    op.drop_column("bank_accounts", "fintoc_link_id")
    op.drop_column("bank_accounts", "fintoc_account_id")
    op.drop_column("bank_accounts", "import_status")
    op.drop_column("bank_accounts", "last_synced_at")
    op.drop_column("bank_accounts", "import_started_at")
    op.drop_column("bank_accounts", "balance_available")
    op.drop_column("bank_accounts", "balance_current")

    # --- Drop Fintoc column from transactions ---
    op.drop_column("transactions", "fintoc_id")

    # --- Add source_type to transactions ---
    op.add_column(
        "transactions",
        sa.Column("source_type", sa.String(), nullable=False, server_default="email"),
    )

    # --- Create bank_credentials table ---
    op.create_table(
        "bank_credentials",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("bank_code", sa.String(), nullable=False),
        sa.Column("encrypted_rut", sa.LargeBinary(), nullable=False),
        sa.Column("encrypted_password", sa.LargeBinary(), nullable=False),
        sa.Column("encryption_iv", sa.LargeBinary(), nullable=False),
        sa.Column("next_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_status", sa.String(), nullable=True),
        sa.Column("current_job_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "bank_code"),
    )

    # --- RLS policy for bank_credentials ---
    op.execute("ALTER TABLE bank_credentials ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY bank_credentials_user_policy ON bank_credentials
        FOR ALL USING (user_id = auth.uid());
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS bank_credentials_user_policy ON bank_credentials;")
    op.execute("ALTER TABLE bank_credentials DISABLE ROW LEVEL SECURITY;")
    op.drop_table("bank_credentials")
    op.drop_column("transactions", "source_type")
    op.add_column("transactions", sa.Column("fintoc_id", sa.String(), nullable=True))
    op.add_column("bank_accounts", sa.Column("balance_current", sa.Integer(), nullable=True))
    op.add_column("bank_accounts", sa.Column("balance_available", sa.Integer(), nullable=True))
    op.add_column(
        "bank_accounts", sa.Column("import_started_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "bank_accounts", sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "bank_accounts",
        sa.Column("import_status", sa.String(), nullable=False, server_default="done"),
    )
    op.add_column("bank_accounts", sa.Column("fintoc_account_id", sa.String(), nullable=True))
    op.add_column("bank_accounts", sa.Column("fintoc_link_id", sa.String(), nullable=True))
