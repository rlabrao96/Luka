"""Create notification_preferences table with RLS.

Revision ID: 014
Revises: 013
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "014"
down_revision = "013"


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True
        ),
        sa.Column("whatsapp_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.execute("ALTER TABLE notification_preferences ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY notification_preferences_user_policy ON notification_preferences
        FOR ALL USING (user_id = auth.uid())
    """)


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS notification_preferences_user_policy ON notification_preferences"
    )
    op.drop_table("notification_preferences")
