import uuid
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from core.database import Base


class BankRegistry(Base):
    __tablename__ = "bank_registry"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bank_domain = Column(String, unique=True, nullable=False, index=True)
    bank_name = Column(String, nullable=False)
    country = Column(String(2), nullable=False, index=True)
    known_subjects = Column(JSONB, default=list)
    notification_types = Column(JSONB, default=list)
    active_template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("email_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    email_count = Column(Integer, default=0)
    status = Column(String, default="active")  # active | push_only | deprecated
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bank_domain = Column(String, nullable=False, index=True)
    country = Column(String(2), nullable=False)
    template_code = Column(JSONB, nullable=False)  # declarative extraction template
    template_hash = Column(String(64), nullable=False)
    status = Column(String, default="candidate")  # candidate | active | retired | failed
    validated_count = Column(Integer, default=0)
    accuracy = Column(Float, default=0.0)
    promoted_at = Column(DateTime(timezone=True), nullable=True)
    retired_at = Column(DateTime(timezone=True), nullable=True)
    retired_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ParsedEmailLog(Base):
    __tablename__ = "parsed_email_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    bank_domain = Column(String, nullable=False, index=True)
    country = Column(String(2), nullable=True)
    raw_email_html = Column(Text, nullable=True)  # purged after 7 days
    llm_extraction = Column(JSONB, nullable=True)
    template_extraction = Column(JSONB, nullable=True)
    parser_used = Column(String, nullable=False)  # llm | template | regex
    llm_model_used = Column(String, nullable=True)
    shadow_match = Column(Boolean, nullable=True)
    waterfall_depth = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
