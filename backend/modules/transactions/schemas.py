import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field


class TransactionResponse(BaseModel):
    id: uuid.UUID
    raw_merchant_name: str
    amount: Decimal
    currency: str
    transaction_date: datetime
    category: str | None
    source: str
    source_type: str | None = None
    status: str
    split_type: str | None = None
    bank_name: str | None = None
    bank_account_id: uuid.UUID | None = None
    account_kind: str | None = None
    transaction_type: str | None = None
    display_name: str | None = None
    # Pair ids (Task 4.5): used by the frontend to group CC transfers and
    # refunds into a single visual row. Null for unpaired transactions.
    transfer_pair_id: uuid.UUID | None = None
    refund_pair_id: uuid.UUID | None = None
    # Lifecycle timestamps (Task 4.6): `created_at` backs the "backlog age"
    # badge on PendingBlock (how long a pending row has been sitting).
    # `orphaned_at` is when a row transitioned into `status='orphan'`.
    created_at: datetime | None = None
    orphaned_at: datetime | None = None

    model_config = {"from_attributes": True}


class CategoryUpdateRequest(BaseModel):
    category: str | None


class SplitTypeUpdateRequest(BaseModel):
    split_type: Literal["personal", "shared", "partner"]


class PendingTransactionsResponse(BaseModel):
    awaiting_reconciliation: list[TransactionResponse] = []
    needs_classification: list[TransactionResponse] = []
    unmatched_email: list[TransactionResponse] = []


class MatchCandidate(BaseModel):
    id: uuid.UUID
    bank_account_id: uuid.UUID | None
    bank_account_name: str | None
    transaction_date: datetime
    amount: Decimal
    currency: str
    raw_merchant_name: str
    category: str | None = None
    status: str | None = None

    model_config = {"from_attributes": True}


class LinkRequest(BaseModel):
    bank_transaction_id: uuid.UUID


class BulkActionRequest(BaseModel):
    transaction_ids: list[uuid.UUID] = Field(..., min_length=1)
    action: Literal["dismiss", "delete"]


class BulkActionResponse(BaseModel):
    processed: int
