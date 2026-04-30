"""046 — create eight trip tables (Viajes)

Revision ID: 046
Revises: 045

Creates the schema backing the Viajes (Trips) feature:

  trips, trip_attendees, trip_expenses, trip_expense_splits,
  trip_settlements, trip_suggestion_dismissals,
  trip_settlement_dismissals, trip_base_currency_changes

This migration only sets up tables, columns, FKs, CHECKs and indexes.
RLS policies (Task 1.3) and mutual-exclusivity / state-machine triggers
(Task 1.4) are applied in follow-up migrations.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision = "046"
down_revision = "045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. trips ---------------------------------------------------------------
    op.create_table(
        "trips",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "creator_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("base_currency", sa.CHAR(length=3), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column("invite_token_hash", sa.Text(), nullable=True),
        sa.Column("invite_token_expires_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("end_date >= start_date", name="ck_trips_dates"),
    )
    op.create_index(
        "ux_trips_invite_token_hash",
        "trips",
        ["invite_token_hash"],
        unique=True,
        postgresql_where=sa.text("invite_token_hash IS NOT NULL"),
    )

    # 2. trip_attendees ------------------------------------------------------
    op.create_table(
        "trip_attendees",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "trip_id",
            UUID(as_uuid=True),
            sa.ForeignKey("trips.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_trip_attendees_trip_id",
        "trip_attendees",
        ["trip_id"],
    )
    op.create_index(
        "ux_trip_attendees_trip_user",
        "trip_attendees",
        ["trip_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )

    # 3. trip_expenses -------------------------------------------------------
    op.create_table(
        "trip_expenses",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "trip_id",
            UUID(as_uuid=True),
            sa.ForeignKey("trips.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "payer_attendee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("trip_attendees.id"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column(
            "transaction_id",
            UUID(as_uuid=True),
            sa.ForeignKey("transactions.id"),
            nullable=True,
        ),
        sa.Column("fx_rate_to_base", sa.Numeric(20, 10), nullable=True),
        sa.Column(
            "created_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_trip_expenses_amount_positive"),
    )
    op.create_index(
        "ix_trip_expenses_trip_id",
        "trip_expenses",
        ["trip_id"],
    )
    op.create_index(
        "ux_trip_expenses_transaction_id",
        "trip_expenses",
        ["transaction_id"],
        unique=True,
        postgresql_where=sa.text("transaction_id IS NOT NULL AND deleted_at IS NULL"),
    )

    # 4. trip_expense_splits -------------------------------------------------
    op.create_table(
        "trip_expense_splits",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "trip_expense_id",
            UUID(as_uuid=True),
            sa.ForeignKey("trip_expenses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "attendee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("trip_attendees.id"),
            nullable=False,
        ),
        sa.Column("share_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("share_type", sa.String(length=24), nullable=False),
        sa.UniqueConstraint(
            "trip_expense_id",
            "attendee_id",
            name="ux_trip_expense_splits_expense_attendee",
        ),
    )
    op.create_index(
        "ix_trip_expense_splits_expense_id",
        "trip_expense_splits",
        ["trip_expense_id"],
    )

    # 5. trip_settlements ----------------------------------------------------
    op.create_table(
        "trip_settlements",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "trip_id",
            UUID(as_uuid=True),
            sa.ForeignKey("trips.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_attendee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("trip_attendees.id"),
            nullable=False,
        ),
        sa.Column(
            "to_attendee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("trip_attendees.id"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), nullable=False),
        sa.Column("fx_rate_to_base", sa.Numeric(20, 10), nullable=True),
        sa.Column(
            "settled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "transaction_id",
            UUID(as_uuid=True),
            sa.ForeignKey("transactions.id"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "write_off",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("amount > 0", name="ck_trip_settlements_amount_positive"),
        sa.CheckConstraint(
            "from_attendee_id <> to_attendee_id",
            name="ck_trip_settlements_distinct_attendees",
        ),
    )
    op.create_index(
        "ix_trip_settlements_trip_id",
        "trip_settlements",
        ["trip_id"],
    )

    # 6. trip_suggestion_dismissals -----------------------------------------
    op.create_table(
        "trip_suggestion_dismissals",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "trip_id",
            UUID(as_uuid=True),
            sa.ForeignKey("trips.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "transaction_id",
            UUID(as_uuid=True),
            sa.ForeignKey("transactions.id"),
            nullable=False,
        ),
        sa.Column(
            "dismissed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint(
            "user_id",
            "trip_id",
            "transaction_id",
            name="pk_trip_suggestion_dismissals",
        ),
    )

    # 7. trip_settlement_dismissals -----------------------------------------
    op.create_table(
        "trip_settlement_dismissals",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "transaction_id",
            UUID(as_uuid=True),
            sa.ForeignKey("transactions.id"),
            nullable=False,
        ),
        sa.Column(
            "dismissed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint(
            "user_id",
            "transaction_id",
            name="pk_trip_settlement_dismissals",
        ),
    )

    # 8. trip_base_currency_changes -----------------------------------------
    op.create_table(
        "trip_base_currency_changes",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "trip_id",
            UUID(as_uuid=True),
            sa.ForeignKey("trips.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("old_currency", sa.CHAR(length=3), nullable=False),
        sa.Column("new_currency", sa.CHAR(length=3), nullable=False),
        sa.Column("cross_rate", sa.Numeric(20, 10), nullable=False),
        sa.Column(
            "changed_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_trip_base_currency_changes_trip_id",
        "trip_base_currency_changes",
        ["trip_id"],
    )


def downgrade() -> None:
    # Drop in reverse creation order to respect FK dependencies.
    op.drop_index(
        "ix_trip_base_currency_changes_trip_id",
        table_name="trip_base_currency_changes",
    )
    op.drop_table("trip_base_currency_changes")

    op.drop_table("trip_settlement_dismissals")
    op.drop_table("trip_suggestion_dismissals")

    op.drop_index("ix_trip_settlements_trip_id", table_name="trip_settlements")
    op.drop_table("trip_settlements")

    op.drop_index(
        "ix_trip_expense_splits_expense_id",
        table_name="trip_expense_splits",
    )
    op.drop_table("trip_expense_splits")

    op.drop_index("ux_trip_expenses_transaction_id", table_name="trip_expenses")
    op.drop_index("ix_trip_expenses_trip_id", table_name="trip_expenses")
    op.drop_table("trip_expenses")

    op.drop_index("ux_trip_attendees_trip_user", table_name="trip_attendees")
    op.drop_index("ix_trip_attendees_trip_id", table_name="trip_attendees")
    op.drop_table("trip_attendees")

    op.drop_index("ux_trips_invite_token_hash", table_name="trips")
    op.drop_table("trips")
