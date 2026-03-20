"""performance_indexes

Revision ID: 008
Revises: 007
Create Date: 2026-03-20

Add indexes on all high-frequency query columns identified in performance audit.
These cover FK columns used in WHERE/JOIN clauses, idempotency lookups,
merchant normalization, and Fintoc reconciliation.
"""

from typing import Sequence, Union
from alembic import op

revision: str = "008"
down_revision: Union[str, Sequence[str], None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── transactions ───────────────────────────────────────────────────────────
    # GET /transactions/mine filters on user_id (called on every dashboard load)
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"])
    # GET /transactions/shared filters on household_id
    op.create_index("ix_transactions_household_id", "transactions", ["household_id"])
    # Fintoc reconciler checks fintoc_id on every imported transaction
    op.create_index("ix_transactions_fintoc_id", "transactions", ["fintoc_id"])
    # Monthly summary query filters on transaction_date
    op.create_index("ix_transactions_transaction_date", "transactions", ["transaction_date"])

    # ── transaction_splits ─────────────────────────────────────────────────────
    # Joins to transactions on transaction_id in nearly every query
    op.create_index(
        "ix_transaction_splits_transaction_id", "transaction_splits", ["transaction_id"]
    )

    # ── household_members ──────────────────────────────────────────────────────
    # require_membership() is the primary auth check — called on every protected endpoint
    # Composite index covers the exact (household_id, user_id) filter pattern
    op.create_index(
        "ix_household_members_household_user",
        "household_members",
        ["household_id", "user_id"],
    )

    # ── bank_accounts ──────────────────────────────────────────────────────────
    # GET /bank-accounts filters on household_id + is_active
    op.create_index("ix_bank_accounts_household_id", "bank_accounts", ["household_id"])
    # Fintoc webhook deduplication checks fintoc_account_id
    op.create_index("ix_bank_accounts_fintoc_account_id", "bank_accounts", ["fintoc_account_id"])

    # ── processed_webhooks ─────────────────────────────────────────────────────
    # Idempotency check on every webhook — message_id is the PK but an explicit
    # index ensures fast lookups even with PgBouncer
    op.create_index("ix_processed_webhooks_message_id", "processed_webhooks", ["message_id"])

    # ── merchants ──────────────────────────────────────────────────────────────
    # lookup_merchant() queries normalized_name on every transaction
    op.create_index("ix_merchants_normalized_name", "merchants", ["normalized_name"])

    # ── users ──────────────────────────────────────────────────────────────────
    # get_current_user() looks up user by email on every authenticated request
    op.create_index("ix_users_email", "users", ["email"])
    # Outlook webhook finds user by mail_watch_subscription_id on every notification
    op.create_index("ix_users_mail_watch_subscription_id", "users", ["mail_watch_subscription_id"])

    # ── household_invites ──────────────────────────────────────────────────────
    # accept_invite() looks up by token
    op.create_index("ix_household_invites_token", "household_invites", ["token"])


def downgrade() -> None:
    op.drop_index("ix_transactions_user_id", "transactions")
    op.drop_index("ix_transactions_household_id", "transactions")
    op.drop_index("ix_transactions_fintoc_id", "transactions")
    op.drop_index("ix_transactions_transaction_date", "transactions")
    op.drop_index("ix_transaction_splits_transaction_id", "transaction_splits")
    op.drop_index("ix_household_members_household_user", "household_members")
    op.drop_index("ix_bank_accounts_household_id", "bank_accounts")
    op.drop_index("ix_bank_accounts_fintoc_account_id", "bank_accounts")
    op.drop_index("ix_processed_webhooks_message_id", "processed_webhooks")
    op.drop_index("ix_merchants_normalized_name", "merchants")
    op.drop_index("ix_users_email", "users")
    op.drop_index("ix_users_mail_watch_subscription_id", "users")
    op.drop_index("ix_household_invites_token", "household_invites")
