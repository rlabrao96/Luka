"""050 — cascade behavior for trip → transactions FKs

Revision ID: 050
Revises: 049

Migration 046 created four FKs from trip-side tables back to
``transactions.id`` without ON DELETE behavior, which defaults to
``NO ACTION`` and blocks ``DELETE FROM transactions`` whenever any of
those rows reference the txn. The Plaid sync legitimately deletes
pending transactions when a settled version replaces them
(``modules/plaid/sync.py`` ~line 335), so any user who has dismissed a
trip suggestion or linked a trip expense / settlement against a
pending txn now breaks the next Plaid sync with a 23503
ForeignKeyViolation.

Cascade choices:

* ``trip_suggestion_dismissals.transaction_id`` → CASCADE.
  A dismissal record loses meaning the moment the txn is gone — the
  replacement will generate a fresh suggestion the user can re-dismiss.

* ``trip_settlement_dismissals.transaction_id`` → CASCADE.
  Same reasoning — settlement-suggestion dismissals are per-txn signals.

* ``trip_expenses.transaction_id`` → SET NULL.
  The trip expense itself should survive (the user already attributed
  the cost to the trip ledger). Becoming a manual stub is the safe
  fallback. Plaid sync ALSO re-links to the replacement when one is
  found (companion change in ``sync.py``), so this only fires when the
  txn is removed without a replacement.

* ``trip_settlements.transaction_id`` → SET NULL. Same reasoning.
"""

from alembic import op


revision = "050"
down_revision = "049"
branch_labels = None
depends_on = None


_DROPS_AND_RECREATES = [
    # (table, old_constraint_name, new_constraint_name, on_delete)
    (
        "trip_suggestion_dismissals",
        "trip_suggestion_dismissals_transaction_id_fkey",
        "trip_suggestion_dismissals_transaction_id_fkey",
        "CASCADE",
    ),
    (
        "trip_settlement_dismissals",
        "trip_settlement_dismissals_transaction_id_fkey",
        "trip_settlement_dismissals_transaction_id_fkey",
        "CASCADE",
    ),
    (
        "trip_expenses",
        "trip_expenses_transaction_id_fkey",
        "trip_expenses_transaction_id_fkey",
        "SET NULL",
    ),
    (
        "trip_settlements",
        "trip_settlements_transaction_id_fkey",
        "trip_settlements_transaction_id_fkey",
        "SET NULL",
    ),
]


def upgrade() -> None:
    for table, old_name, new_name, on_delete in _DROPS_AND_RECREATES:
        op.execute(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS "{old_name}"')
        op.execute(
            f"ALTER TABLE {table} "
            f'ADD CONSTRAINT "{new_name}" '
            f"FOREIGN KEY (transaction_id) "
            f"REFERENCES transactions(id) ON DELETE {on_delete}"
        )


def downgrade() -> None:
    for table, _old_name, new_name, _on_delete in _DROPS_AND_RECREATES:
        op.execute(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS "{new_name}"')
        op.execute(
            f"ALTER TABLE {table} "
            f'ADD CONSTRAINT "{new_name}" '
            f"FOREIGN KEY (transaction_id) "
            f"REFERENCES transactions(id)"
        )
