import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class CanonicalMerchant(Base):
    __tablename__ = "canonical_merchants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    default_category: Mapped[str | None] = mapped_column(String, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    review_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("merchant_review_jobs.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MerchantReviewJob(Base):
    __tablename__ = "merchant_review_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    bank_credential_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bank_credentials.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String, default="processing")
    total_merchants: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewed_count: Mapped[int] = mapped_column(Integer, default=0)
    notification_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("notifications.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
