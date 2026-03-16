import uuid
from datetime import date
from pydantic import BaseModel


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
