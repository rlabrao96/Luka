"""Create user_category_preferences table with RLS.

Revision ID: 015
Revises: 014
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "015"
down_revision = "014"


def upgrade() -> None:
    op.create_table(
        "user_category_preferences",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "category", name="uq_user_category_prefs"),
    )
    op.execute("ALTER TABLE user_category_preferences ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY user_category_preferences_user_policy ON user_category_preferences
        FOR ALL USING (user_id = auth.uid())
    """)


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS user_category_preferences_user_policy ON user_category_preferences"
    )
    op.drop_table("user_category_preferences")
