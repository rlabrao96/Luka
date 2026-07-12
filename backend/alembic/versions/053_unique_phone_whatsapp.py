"""053 — unique phone_whatsapp per user

Revision ID: 053
Revises: 052

Inbound WhatsApp routing finds the user by phone with LIMIT 1, so two users
verifying the same number means one silently wins and the other's messages
(and manually-logged expenses) land on the wrong account. Enforce uniqueness.

Self-healing: if production already has duplicate verified numbers, keep the
EARLIEST-created user's number and clear the rest (setting whatsapp_verified
false so they re-verify) — otherwise the unique index creation would fail and
take down the whole deploy's release phase.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "053"
down_revision: Union[str, Sequence[str], None] = "052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Dedup: for each phone shared by >1 user, keep the oldest (created_at ASC,
    # id as tiebreak) and clear the others.
    op.execute(
        """
        UPDATE users
        SET phone_whatsapp = NULL, whatsapp_verified = FALSE
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY phone_whatsapp
                           ORDER BY created_at ASC, id
                       ) AS rn
                FROM users
                WHERE phone_whatsapp IS NOT NULL
            ) ranked
            WHERE ranked.rn > 1
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_phone_whatsapp "
        "ON users (phone_whatsapp) WHERE phone_whatsapp IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_users_phone_whatsapp")
