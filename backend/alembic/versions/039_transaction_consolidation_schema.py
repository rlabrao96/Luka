"""Transaction consolidation schema — card_last_four, refund_pair_id, orphan status.

Phase 1 of the transaction consolidation fix. Introduces the data model the rest
of the workflow depends on:

- Canonicalises the status vocabulary to ('pending','settled','orphan'). Legacy
  rows using 'confirmed' are rewritten to 'settled'.
- Adds card_last_four so email-only rows can be matched against bank-connect /
  Plaid rows that know the PAN suffix.
- Adds refund_pair_id, mirroring transfer_pair_id, to link a charge to its
  matching refund so reports can net them out.
- Adds orphaned_at / dismissed_by_user so the UI can surface and clear rows that
  never reconcile without deleting evidence.
- Enables pg_trgm and adds supporting indexes (household+date DESC hot path,
  partial indexes on pending rows and each pair-id, GIN trigram on raw merchant
  name for fuzzy search).

Revision ID: 039
Revises: 038
Create Date: 2026-04-20
"""

from alembic import op


revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Trigram extension for fuzzy merchant-name search.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # New columns.
    op.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS card_last_four VARCHAR(4) NULL")
    op.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS refund_pair_id UUID NULL")
    op.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS orphaned_at TIMESTAMPTZ NULL")
    op.execute(
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS dismissed_by_user "
        "BOOLEAN NOT NULL DEFAULT false"
    )

    # Rewrite legacy 'confirmed' → 'settled' before tightening the CHECK.
    op.execute("UPDATE transactions SET status = 'settled' WHERE status = 'confirmed'")

    # Drop any prior status CHECK constraint (name unknown historically), then add the new one.
    op.execute("ALTER TABLE transactions DROP CONSTRAINT IF EXISTS ck_transactions_status")
    op.execute("ALTER TABLE transactions DROP CONSTRAINT IF EXISTS ck_transaction_status")
    op.execute(
        "ALTER TABLE transactions ADD CONSTRAINT ck_transactions_status "
        "CHECK (status IN ('pending','settled','orphan'))"
    )

    # Hot-path index for the dashboard: household feed ordered by date DESC.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_transactions_household_date "
        "ON transactions (household_id, transaction_date DESC)"
    )
    # Partial index to speed up the pending-inbox query per user.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_transactions_user_pending "
        "ON transactions (user_id) WHERE status = 'pending'"
    )
    # Partial index on transfer_pair_id (reconciling both legs).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_transactions_transfer_pair "
        "ON transactions (transfer_pair_id) WHERE transfer_pair_id IS NOT NULL"
    )
    # Partial index on refund_pair_id (mirror of transfer pair).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_transactions_refund_pair "
        "ON transactions (refund_pair_id) WHERE refund_pair_id IS NOT NULL"
    )
    # GIN trigram index for fuzzy merchant-name matching.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_transactions_raw_merchant_trgm "
        "ON transactions USING gin (raw_merchant_name gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_transactions_raw_merchant_trgm")
    op.execute("DROP INDEX IF EXISTS ix_transactions_refund_pair")
    op.execute("DROP INDEX IF EXISTS ix_transactions_transfer_pair")
    op.execute("DROP INDEX IF EXISTS ix_transactions_user_pending")
    op.execute("DROP INDEX IF EXISTS ix_transactions_household_date")

    op.execute("ALTER TABLE transactions DROP CONSTRAINT IF EXISTS ck_transactions_status")
    # Best-effort restore of prior vocabulary so rollbacks don't leave the app
    # confused. 'orphan' had no prior equivalent — fall back to 'pending'.
    op.execute("UPDATE transactions SET status = 'confirmed' WHERE status = 'settled'")
    op.execute("UPDATE transactions SET status = 'pending' WHERE status = 'orphan'")

    op.execute("ALTER TABLE transactions DROP COLUMN IF EXISTS dismissed_by_user")
    op.execute("ALTER TABLE transactions DROP COLUMN IF EXISTS orphaned_at")
    op.execute("ALTER TABLE transactions DROP COLUMN IF EXISTS refund_pair_id")
    op.execute("ALTER TABLE transactions DROP COLUMN IF EXISTS card_last_four")

    # We deliberately do not DROP EXTENSION pg_trgm — other migrations/tooling
    # may depend on it, and extensions are cheap to leave installed.
