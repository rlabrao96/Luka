"""Add canonical_merchants, notifications, merchant_review_jobs tables."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from alembic import op

revision = "022"
down_revision = "021"


def upgrade() -> None:
    # canonical_merchants
    op.create_table(
        "canonical_merchants",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("display_name", sa.String(), nullable=False, unique=True),
        sa.Column("default_category", sa.String(), nullable=True),
        sa.Column("logo_url", sa.String(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # notifications
    op.create_table(
        "notifications",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column("status", sa.String(), server_default="unread", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notifications_user_status", "notifications", ["user_id", "status"])

    # merchant_review_jobs
    op.create_table(
        "merchant_review_jobs",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "bank_credential_id",
            UUID(as_uuid=True),
            sa.ForeignKey("bank_credentials.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(), server_default="processing", nullable=False),
        sa.Column("total_merchants", sa.Integer(), nullable=True),
        sa.Column("reviewed_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "notification_id", UUID(as_uuid=True), sa.ForeignKey("notifications.id"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Add FK column to merchants
    op.add_column(
        "merchants",
        sa.Column(
            "canonical_merchant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("canonical_merchants.id"),
            nullable=True,
        ),
    )

    # Add review_job_id to canonical_merchants so we can scope review cards per job
    op.add_column(
        "canonical_merchants",
        sa.Column(
            "review_job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("merchant_review_jobs.id"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("canonical_merchants", "review_job_id")
    op.drop_column("merchants", "canonical_merchant_id")
    op.drop_table("merchant_review_jobs")
    op.drop_index("ix_notifications_user_status", "notifications")
    op.drop_table("notifications")
    op.drop_table("canonical_merchants")
