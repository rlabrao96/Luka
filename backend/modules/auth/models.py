import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    phone_whatsapp: Mapped[str | None] = mapped_column(String, nullable=True)
    whatsapp_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_provider: Mapped[str] = mapped_column(String, default="gmail")
    mail_watch_subscription_id: Mapped[str | None] = mapped_column(String, nullable=True)
    mail_watch_expiry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    google_access_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_refresh_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
