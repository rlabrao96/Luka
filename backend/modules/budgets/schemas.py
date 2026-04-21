import uuid
from datetime import date
from pydantic import BaseModel, Field, field_validator

from modules.auth.schemas import ALLOWED_CURRENCIES


class BudgetStatusResponse(BaseModel):
    household_id: str
    month: str
    budgeted: float
    spent: float
    available: float
    percent_used: float


class SetBudgetRequest(BaseModel):
    bank_account_id: uuid.UUID
    month: date
    amount: float


# ── Category budget schemas ──


class CategoryBudgetItem(BaseModel):
    category: str = Field(min_length=1, max_length=64)
    amount: float = Field(ge=0)
    currency: str = Field(default="CLP", min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, v: str) -> str:
        code = v.upper()
        if code not in ALLOWED_CURRENCIES:
            raise ValueError(f"unsupported currency: {v}")
        return code


class CategoryBudgetResponse(BaseModel):
    household_id: str
    month: str
    budgets: list[CategoryBudgetItem]


class SetCategoryBudgetRequest(BaseModel):
    month: date
    budgets: list[CategoryBudgetItem] = Field(max_length=200)
