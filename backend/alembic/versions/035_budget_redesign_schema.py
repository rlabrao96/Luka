"""Budget redesign — contribution modes, user_budget_settings, cuota_purchases

Revision ID: 035
Revises: 034
Create Date: 2026-04-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # household_members
    op.add_column(
        "household_members",
        sa.Column(
            "contribution_mode",
            sa.String(16),
            nullable=False,
            server_default="full",
        ),
    )
    op.create_check_constraint(
        "ck_household_members_contribution_mode",
        "household_members",
        "contribution_mode IN ('full','fixed','reimbursement')",
    )
    op.add_column(
        "household_members",
        sa.Column("fixed_contribution_amount", sa.Numeric(14, 2), nullable=True),
    )
    op.add_column(
        "household_members",
        sa.Column("fixed_contribution_currency", sa.String(3), nullable=True),
    )

    # user_budget_settings
    op.create_table(
        "user_budget_settings",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("savings_target_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("savings_target_currency", sa.String(3), nullable=True),
        sa.Column("payday_day_of_month", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "payday_day_of_month BETWEEN 1 AND 31",
            name="ck_user_budget_settings_payday",
        ),
    )

    # cuota_purchases
    op.create_table(
        "cuota_purchases",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "household_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("households.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "origin_transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transactions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("merchant_name", sa.Text, nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("installments_total", sa.Integer, nullable=False),
        sa.Column("installments_paid", sa.Integer, nullable=False, server_default="0"),
        sa.Column("monthly_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("first_cuota_date", sa.Date, nullable=False),
        sa.Column("last_cuota_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("split_type", sa.String(16), nullable=False, server_default="personal"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("installments_total > 0", name="ck_cuota_installments_total_positive"),
        sa.CheckConstraint(
            "installments_paid >= 0 AND installments_paid <= installments_total",
            name="ck_cuota_installments_paid_range",
        ),
        sa.CheckConstraint("status IN ('active','completed','cancelled')", name="ck_cuota_status"),
        sa.CheckConstraint("split_type IN ('personal','shared')", name="ck_cuota_split_type"),
    )
    op.create_index("ix_cuota_purchases_user_status", "cuota_purchases", ["user_id", "status"])
    op.create_index(
        "ix_cuota_purchases_household_status",
        "cuota_purchases",
        ["household_id", "status"],
    )
    op.create_index("ix_cuota_purchases_last_cuota_date", "cuota_purchases", ["last_cuota_date"])


def downgrade() -> None:
    op.drop_index("ix_cuota_purchases_last_cuota_date", table_name="cuota_purchases")
    op.drop_index("ix_cuota_purchases_household_status", table_name="cuota_purchases")
    op.drop_index("ix_cuota_purchases_user_status", table_name="cuota_purchases")
    op.drop_table("cuota_purchases")
    op.drop_table("user_budget_settings")
    op.drop_constraint(
        "ck_household_members_contribution_mode",
        "household_members",
        type_="check",
    )
    op.drop_column("household_members", "fixed_contribution_currency")
    op.drop_column("household_members", "fixed_contribution_amount")
    op.drop_column("household_members", "contribution_mode")
