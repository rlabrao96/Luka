from pydantic import BaseModel


class ReviewCardResponse(BaseModel):
    canonical_merchant_id: str
    display_name: str
    default_category: str | None = None
    llm_suggested_categories: list[str] = []
    raw_names: list[str] = []
    transaction_count: int = 0
    total_amount: float = 0.0
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
