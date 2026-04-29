"""042 — add transactions.user_edited_fields

Revision ID: 042
Revises: 1d4edef10702

User-edit-wins invariant: when a user touches a field on a transaction
(category, split_type, merchant_name, transaction_type, transfer_to_account_id)
the consolidation/dedup pipeline must never silently overwrite that field.

We track this via a JSONB map of per-field boolean flags. Only fields the
user has touched are present in the map. Per-field timestamps were
considered but YAGNI for now — a boolean is enough for the merge rule.

Example payload after a user edits category and merchant name:

    {"category": true, "merchant_name": true}
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op


revision = "042"
down_revision = "1d4edef10702"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "user_edited_fields",
            JSONB,
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("transactions", "user_edited_fields")
