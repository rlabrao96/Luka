import uuid
from decimal import Decimal
from datetime import datetime
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bank_accounts.id"), nullable=True
    )
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("merchants.id"), nullable=True)
    raw_merchant_name: Mapped[str] = mapped_column(String, nullable=False)
    # Integer MINOR units (cents for 2-decimal currencies, whole units for
    # CLP/COP). Numeric returns Decimal at runtime — annotate honestly so type
    # checkers flag float arithmetic on money.
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String, default="CLP")
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    category: Mapped[str | None] = mapped_column(String, nullable=True)  # denormalized
    source: Mapped[str] = mapped_column(String, nullable=False)  # gmail|outlook|connect|manual
    source_type: Mapped[str] = mapped_column(
        String, nullable=False, default="email", server_default="email"
    )
    status: Mapped[str] = mapped_column(String, default="pending")
    transaction_type: Mapped[str] = mapped_column(String(10), nullable=False, default="expense")
    transfer_to_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bank_accounts.id", ondelete="SET NULL"), nullable=True
    )
    source_bank_name: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_email_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    transfer_pair_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    refund_pair_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # User-declared reimbursement grouping (migration 044). N+1 transactions
    # share the same UUID when one inflow nets out N expenses (e.g. work/school
    # paying back receipts). Excluded from spending totals like transfer/refund
    # pairs. Distinct semantics — see service.link_reimbursement_group.
    reimbursement_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    card_last_four: Mapped[str | None] = mapped_column(String(4), nullable=True)
    orphaned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_by_user: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    plaid_transaction_id: Mapped[str | None] = mapped_column(String, nullable=True, unique=False)
    # User-edit-wins invariant: per-field boolean flags marking fields the user has
    # touched. Consolidation/dedup must never overwrite a field whose flag is True.
    # Keys: "merchant_name" | "category" | "split_type" | "transaction_type"
    #       | "transfer_to_account_id". Absent key == not user-edited.
    user_edited_fields: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    # Idempotency marker — set when this Plaid/bank row has consumed an email
    # match. Future reconciliation passes skip rows where this is non-null.
    matched_email_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Shared-card charge classification (migration 056). Set true when the
    # charge lands on a `shared_card` bank account and hasn't been sorted yet
    # into personal/shared/reimbursable/attributed. No downstream logic reads
    # this in Task 1 — storage only.
    needs_classification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TransactionSplit(Base):
    __tablename__ = "transaction_splits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    split_type: Mapped[str] = mapped_column(String, nullable=False)  # personal|partner|shared
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    whatsapp_message_id: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TransactionAttribution(Base):
    """A transaction on a shared card handed off to a household partner.

    One row per transaction (unique). 'active' → counts for the recipient;
    'rejected' → bounced back to the sender (row kept so a re-hand-off can
    reactivate it). The row's presence is what distinguishes a handed-off
    ``split_type='partner'`` transaction from an exclude-only one.
    """

    __tablename__ = "transaction_attributions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    attributed_to_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    attributed_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="active", server_default="active"
    )  # active|rejected
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProcessedWebhook(Base):
    __tablename__ = "processed_webhooks"

    message_id: Mapped[str] = mapped_column(String, primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class FailedJob(Base):
    __tablename__ = "failed_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_name: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_failed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
