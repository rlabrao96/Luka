import uuid
from datetime import date
from pydantic import BaseModel, Field


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


class CategoryBudgetResponse(BaseModel):
    household_id: str
    month: str
    budgets: list[CategoryBudgetItem]


class SetCategoryBudgetRequest(BaseModel):
    month: date
    budgets: list[CategoryBudgetItem] = Field(max_length=200)
