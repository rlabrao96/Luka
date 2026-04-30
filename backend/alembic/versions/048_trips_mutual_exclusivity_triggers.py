"""048 — mutual-exclusivity triggers between trip_expenses and transaction_splits

Revision ID: 048
Revises: 047

In v1 a transaction may either be split through `transaction_splits`
(household / joint-account split) OR linked to a `trip_expenses` row
(trip split), but never both. These two BEFORE triggers enforce that
invariant at the database level so any code path — service, raw SQL,
admin tools — gets the same guarantee.

Trigger 1 (`trg_reject_split_if_trip_linked`): inserting/updating a
`transaction_splits` row whose `transaction_id` is already linked to a
non-deleted `trip_expenses` raises check_violation (23514).

Trigger 2 (`trg_reject_trip_link_if_split_exists`): inserting/updating
`trip_expenses.transaction_id` to a transaction that already has any
`transaction_splits` rows raises check_violation (23514).

The full insert+raise behavioral test ships in Phase 3 Task 3.2 once
the trip / attendee fixtures from Phase 2 are in place; this migration
is verified by a trigger-existence smoke test in
`tests/test_trips_migration.py`.
"""

from alembic import op


revision = "048"
down_revision = "047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- 1. Reject INSERT/UPDATE on transaction_splits if trip-linked ------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.reject_split_if_trip_linked()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $func$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM trip_expenses
                WHERE transaction_id = NEW.transaction_id
                  AND deleted_at IS NULL
            ) THEN
                RAISE EXCEPTION
                    'transaction is linked to a trip; dual-split is not supported in v1'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END
        $func$;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_reject_split_if_trip_linked
            BEFORE INSERT OR UPDATE ON transaction_splits
            FOR EACH ROW EXECUTE FUNCTION public.reject_split_if_trip_linked();
        """
    )

    # ---- 2. Reject trip-link if transaction already has household splits ---
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.reject_trip_link_if_split_exists()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $func$
        BEGIN
            IF NEW.transaction_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM transaction_splits
                WHERE transaction_id = NEW.transaction_id
            ) THEN
                RAISE EXCEPTION
                    'transaction has household splits; cannot tag to a trip in v1'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END
        $func$;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_reject_trip_link_if_split_exists
            BEFORE INSERT OR UPDATE OF transaction_id ON trip_expenses
            FOR EACH ROW EXECUTE FUNCTION public.reject_trip_link_if_split_exists();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_reject_trip_link_if_split_exists ON trip_expenses;")
    op.execute("DROP TRIGGER IF EXISTS trg_reject_split_if_trip_linked ON transaction_splits;")
    op.execute("DROP FUNCTION IF EXISTS public.reject_trip_link_if_split_exists();")
    op.execute("DROP FUNCTION IF EXISTS public.reject_split_if_trip_linked();")
