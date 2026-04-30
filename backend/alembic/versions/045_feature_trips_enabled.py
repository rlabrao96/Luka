"""045 — add users.feature_trips_enabled

Revision ID: 045
Revises: 044

Adds a per-user boolean feature flag (default false) gating the new Viajes
(Trips) section. Phase 1 of the trips rollout — the column is read by the
backend feature-gate dependency and by the frontend nav to show/hide the
section while the feature is shipped behind the flag.
"""

import sqlalchemy as sa
from alembic import op


revision = "045"
down_revision = "044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "feature_trips_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "feature_trips_enabled")
