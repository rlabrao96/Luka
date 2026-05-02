"""049 — narrow trip ↔ split mutex triggers to shared splits only

Revision ID: 049
Revises: 048

Migration 048 introduced two BEFORE triggers that enforce mutual
exclusivity between ``trip_expenses`` and ``transaction_splits``. The
intent (per the v1 spec §3.10) was to block dual-splitting of
**joint-account / shared** transactions — where a real fund division
already exists across household members.

Implementation gap: every Luka transaction has a ``transaction_splits``
row (``split_type='personal'`` for solo accounts, ``'shared'`` for
joint), so the original triggers blocked **all** transactions from
being linked to a trip. A user with a personal Amex transaction would
hit ``joint_account_dual_split_not_supported`` even though their
transaction has no real split — only a personal tag.

This migration narrows both triggers to only consider rows with
``split_type = 'shared'``. Personal splits are tags, not divisions, and
should coexist freely with trip links.

The ``"household splits"`` substring in the RAISE message is preserved
so the service-layer ``IntegrityError`` mapper continues to surface the
409 ``joint_account_dual_split_not_supported`` only for the now-correct
case.
"""

from alembic import op


revision = "049"
down_revision = "048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- 1. Reject INSERT/UPDATE on transaction_splits if trip-linked ------
    # Same as 048: any new transaction_splits row (whether personal or
    # shared) on a trip-linked transaction is still rejected — but in
    # practice only a 'shared' write would race here, since personal
    # rows already exist by the time the trip link is added.
    # We narrow this side too for symmetry: only 'shared' inserts on a
    # trip-linked transaction trigger the violation, which preserves the
    # ability of the existing personal tag to remain alongside the trip.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.reject_split_if_trip_linked()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $func$
        BEGIN
            IF NEW.split_type = 'shared' AND EXISTS (
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

    # ---- 2. Reject trip-link if transaction already has SHARED splits ------
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
                  AND split_type = 'shared'
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


def downgrade() -> None:
    # Restore the 048 (over-broad) versions.
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
