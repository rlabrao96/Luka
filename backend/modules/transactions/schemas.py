import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class TransactionResponse(BaseModel):
    id: uuid.UUID
    raw_merchant_name: str
    amount: Decimal
    currency: str
    transaction_date: datetime
    category: str | None
    source: str
    status: str
    split_type: str | None = None
    bank_name: str | None = None
    bank_account_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class CategoryUpdateRequest(BaseModel):
    category: str | None
