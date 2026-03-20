import uuid
from datetime import datetime, date
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class Household(Base):
    __tablename__ = "households"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # 'individual' | 'couple'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HouseholdMember(Base):
    __tablename__ = "household_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String, default="member")  # 'owner' | 'member'
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HouseholdInvite(Base):
    __tablename__ = "household_invites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    invited_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    invited_email: Mapped[str] = mapped_column(String, nullable=False)
    token: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    bank_name: Mapped[str] = mapped_column(String, nullable=False)
    account_type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # 'personal' | 'partner' | 'joint'
    cardholder_name: Mapped[str | None] = mapped_column(String, nullable=True)
    email_sender_pattern: Mapped[str | None] = mapped_column(String, nullable=True)
    fintoc_link_id: Mapped[str | None] = mapped_column(String, nullable=True)
    fintoc_account_id: Mapped[str | None] = mapped_column(String, nullable=True)
    account_kind: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # 'checking_account' | 'credit_card' | etc
    account_number: Mapped[str | None] = mapped_column(String, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    import_status: Mapped[str] = mapped_column(
        String, nullable=False, default="done", server_default="done"
    )  # 'pending'|'importing'|'done'|'failed'
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    import_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    balance_available: Mapped[int | None] = mapped_column(nullable=True)
    balance_current: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HouseholdBudget(Base):
    __tablename__ = "household_budgets"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "bank_account_id",
            "month",
            name="uq_household_budgets_household_account_month",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    bank_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bank_accounts.id"), nullable=False
    )
    month: Mapped[date] = mapped_column(Date, nullable=False)  # DATE not TIMESTAMP
    budgeted: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    source: Mapped[str] = mapped_column(String, default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HouseholdBudgetAllocation(Base):
    __tablename__ = "household_budget_allocations"
    __table_args__ = (
        UniqueConstraint("household_id", "month", name="uq_budget_allocation_household_month"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )
    month: Mapped[date] = mapped_column(Date, nullable=False)
    hogar_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    ahorro_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    personal_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
