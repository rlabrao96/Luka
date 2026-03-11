"""initial_schema

Revision ID: 001
Revises:
Create Date: 2026-03-11 11:55:11.895882

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all core tables in dependency order."""

    # 1. users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column(
            "whatsapp_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("email_provider", sa.String(), nullable=False, server_default=sa.text("'gmail'")),
        sa.Column("mail_watch_subscription_id", sa.String(), nullable=True),
        sa.Column("mail_watch_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    # 2. households
    op.create_table(
        "households",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # 3. household_members (FK: households, users)
    op.create_table(
        "household_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default=sa.text("'member'")),
        sa.Column(
            "joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(
            ["household_id"], ["households.id"], name="fk_household_members_household_id"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_household_members_user_id"),
    )

    # 4. household_invites (FK: households, users)
    op.create_table(
        "household_invites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invited_email", sa.String(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["household_id"], ["households.id"], name="fk_household_invites_household_id"
        ),
        sa.ForeignKeyConstraint(
            ["invited_by"], ["users.id"], name="fk_household_invites_invited_by"
        ),
        sa.UniqueConstraint("token", name="uq_household_invites_token"),
    )

    # 5. bank_accounts (FK: households, users)
    op.create_table(
        "bank_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_name", sa.String(), nullable=False),
        sa.Column("account_type", sa.String(), nullable=False),
        sa.Column("cardholder_name", sa.String(), nullable=True),
        sa.Column("email_sender_pattern", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["household_id"], ["households.id"], name="fk_bank_accounts_household_id"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_bank_accounts_user_id"),
    )

    # 6. household_budgets (FK: households, bank_accounts)
    op.create_table(
        "household_budgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("budgeted", sa.Numeric(12, 2), nullable=False),
        sa.Column("source", sa.String(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["household_id"], ["households.id"], name="fk_household_budgets_household_id"
        ),
        sa.ForeignKeyConstraint(
            ["bank_account_id"], ["bank_accounts.id"], name="fk_household_budgets_bank_account_id"
        ),
        sa.UniqueConstraint(
            "household_id",
            "bank_account_id",
            "month",
            name="uq_household_budgets_household_account_month",
        ),
    )

    # 7. merchants
    op.create_table(
        "merchants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("raw_name", sa.String(), nullable=False),
        sa.Column("normalized_name", sa.String(), nullable=True),
        sa.Column("llm_suggested_categories", sa.JSON(), nullable=True),
        sa.Column("total_selections", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("raw_name", name="uq_merchants_raw_name"),
    )

    # 8. merchant_category_selections (FK: merchants)
    op.create_table(
        "merchant_category_selections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["merchant_id"], ["merchants.id"], name="fk_merchant_category_selections_merchant_id"
        ),
    )

    # 9. transactions (FK: users, households, bank_accounts, merchants)
    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("raw_merchant_name", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(), nullable=False, server_default=sa.text("'CLP'")),
        sa.Column("transaction_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("fintoc_id", sa.String(), nullable=True),
        sa.Column("raw_email_text", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_transactions_user_id"),
        sa.ForeignKeyConstraint(
            ["household_id"], ["households.id"], name="fk_transactions_household_id"
        ),
        sa.ForeignKeyConstraint(
            ["bank_account_id"], ["bank_accounts.id"], name="fk_transactions_bank_account_id"
        ),
        sa.ForeignKeyConstraint(
            ["merchant_id"], ["merchants.id"], name="fk_transactions_merchant_id"
        ),
    )

    # 10. transaction_splits (FK: transactions, users)
    op.create_table(
        "transaction_splits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("split_type", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("decided_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("whatsapp_message_id", sa.String(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"], ["transactions.id"], name="fk_transaction_splits_transaction_id"
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_user_id"], ["users.id"], name="fk_transaction_splits_decided_by_user_id"
        ),
    )

    # 11. processed_webhooks
    op.create_table(
        "processed_webhooks",
        sa.Column("message_id", sa.String(), primary_key=True),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # 12. failed_jobs
    op.create_table(
        "failed_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_name", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_failed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("failed_jobs")
    op.drop_table("processed_webhooks")
    op.drop_table("transaction_splits")
    op.drop_table("transactions")
    op.drop_table("merchant_category_selections")
    op.drop_table("merchants")
    op.drop_table("household_budgets")
    op.drop_table("bank_accounts")
    op.drop_table("household_invites")
    op.drop_table("household_members")
    op.drop_table("households")
    op.drop_table("users")
