import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class UserBudgetSettings(Base):
    __tablename__ = "user_budget_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    savings_target_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    savings_target_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    personal_allocation_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    personal_allocation_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    payday_day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "payday_day_of_month BETWEEN 1 AND 31",
            name="ck_user_budget_settings_payday",
        ),
    )
