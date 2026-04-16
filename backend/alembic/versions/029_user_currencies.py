"""user_currencies table

Revision ID: 029
Revises: 028
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "029"
down_revision = "028"


def upgrade() -> None:
    op.create_table(
        "user_currencies",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("currency_code", sa.CHAR(3), nullable=False),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("user_id", "currency_code"),
    )
    op.create_index("ix_user_currencies_user_id", "user_currencies", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_currencies_user_id", table_name="user_currencies")
    op.drop_table("user_currencies")
