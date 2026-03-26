import uuid
from decimal import Decimal
from pydantic import BaseModel, EmailStr


class CreateHouseholdRequest(BaseModel):
    name: str
    type: str  # 'individual' | 'couple'


class InviteRequest(BaseModel):
    email: EmailStr


class HouseholdResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: str

    model_config = {"from_attributes": True}


class MemberTotal(BaseModel):
    user_id: str
    full_name: str
    amount: Decimal
    pct: float


class CategoryBreakdownRow(BaseModel):
    category: str
    member_totals: list[MemberTotal]
    total: Decimal
    pct_of_overall: float


class HouseholdSummaryResponse(BaseModel):
    total: Decimal
    members: list[MemberTotal]
    by_category: list[CategoryBreakdownRow]


class SettlementResponse(BaseModel):
    from_user_id: str
    from_user_name: str
    to_user_id: str
    to_user_name: str
    amount: Decimal
    split_ratio: list[int]
    month: str


class SplitRatioRequest(BaseModel):
    ratio: list[int]


class SplitRatioResponse(BaseModel):
    split_ratio: list[int]
