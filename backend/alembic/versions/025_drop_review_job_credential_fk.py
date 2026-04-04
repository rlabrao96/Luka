"""drop FK constraint on merchant_review_jobs.bank_credential_id

Revision ID: 025
Revises: 024
Create Date: 2026-04-04
"""

from alembic import op

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "merchant_review_jobs_bank_credential_id_fkey",
        "merchant_review_jobs",
        type_="foreignkey",
    )


def downgrade() -> None:
    op.create_foreign_key(
        "merchant_review_jobs_bank_credential_id_fkey",
        "merchant_review_jobs",
        "bank_credentials",
        ["bank_credential_id"],
        ["id"],
    )
