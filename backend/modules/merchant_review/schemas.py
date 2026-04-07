from pydantic import BaseModel


class ReviewTransactionInfo(BaseModel):
    raw_name: str
    date: str | None = None
    amount: float = 0.0
    currency: str = "CLP"


class ReviewCardResponse(BaseModel):
    canonical_merchant_id: str
    display_name: str
    default_category: str | None = None
    llm_suggested_categories: list[str] = []
    transactions: list[ReviewTransactionInfo] = []
    transaction_count: int = 0
    total_amount: float = 0.0
    currency: str = "CLP"
    is_verified: bool = False

    model_config = {"from_attributes": True}


class ReviewStatusResponse(BaseModel):
    job_id: str
    status: str  # processing, ready, completed, skipped, failed
    total_merchants: int | None = None
    reviewed_count: int = 0


class MerchantApproval(BaseModel):
    display_name: str | None = None  # None = keep LLM suggestion
    category: str | None = None  # None = keep LLM suggestion
    action: str  # "approve", "skip"
