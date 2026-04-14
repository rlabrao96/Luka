import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class CuotaPurchase(Base):
    __tablename__ = "cuota_purchases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )
    origin_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True
    )
    merchant_name: Mapped[str] = mapped_column(Text, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    installments_total: Mapped[int] = mapped_column(Integer, nullable=False)
    installments_paid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    monthly_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    first_cuota_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_cuota_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    split_type: Mapped[str] = mapped_column(String(16), nullable=False, default="personal")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("installments_total > 0", name="ck_cuota_installments_total_positive"),
        CheckConstraint(
            "installments_paid >= 0 AND installments_paid <= installments_total",
            name="ck_cuota_installments_paid_range",
        ),
        CheckConstraint("status IN ('active','completed','cancelled')", name="ck_cuota_status"),
        CheckConstraint("split_type IN ('personal','shared')", name="ck_cuota_split_type"),
        Index("ix_cuota_purchases_user_status", "user_id", "status"),
        Index("ix_cuota_purchases_household_status", "household_id", "status"),
        Index("ix_cuota_purchases_last_cuota_date", "last_cuota_date"),
    )
