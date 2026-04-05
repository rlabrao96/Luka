import uuid
from datetime import date
from pydantic import BaseModel, model_validator


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


# ── Personal budget schemas ──


class PacePoint(BaseModel):
    day: int
    cumulative_spent: float


class PaceBlock(BaseModel):
    spendable_budget: float
    daily_points: list[PacePoint]
    today_day: int
    days_in_month: int
    pace_at_today: float
    actual_at_today: float
    delta: float
    on_track: bool


class BreakdownBlock(BaseModel):
    household: float
    personal: float


class PersonalBlock(BaseModel):
    ceiling: float
    ceiling_clamped: bool
    spent: float
    breakdown: BreakdownBlock
    available: float
    percent_used: float | None


class HouseholdBlock(BaseModel):
    deposited: float | None
    spent: float
    available: float | None
    percent_used: float | None


class PersonalBudgetResponse(BaseModel):
    mode: str  # 'single' | 'waterfall'
    month: str
    income: float
    personal: PersonalBlock
    pace: PaceBlock
    household: HouseholdBlock | None = None


# ── Allocation schemas ──


class AllocationBlock(BaseModel):
    hogar_pct: float
    ahorro_pct: float
    personal_pct: float
    is_default: bool


class AllocationSuggestion(BaseModel):
    hogar_pct: float
    ahorro_pct: float
    personal_pct: float
    label: str | None = None


class AllocationSuggestions(BaseModel):
    historical: AllocationSuggestion | None
    recommended: AllocationSuggestion


class AllocationResponse(BaseModel):
    month: str
    allocation: AllocationBlock
    suggestions: AllocationSuggestions


class SetAllocationRequest(BaseModel):
    month: date
    hogar_pct: float
    ahorro_pct: float
    personal_pct: float

    @model_validator(mode="after")
    def check_sum(self) -> "SetAllocationRequest":
        total = self.hogar_pct + self.ahorro_pct + self.personal_pct
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"Percentages must sum to 100, got {total}")
        return self


# ── Category budget schemas ──


class CategoryBudgetItem(BaseModel):
    category: str
    amount: float


class CategoryBudgetResponse(BaseModel):
    household_id: str
    month: str
    budgets: list[CategoryBudgetItem]


class SetCategoryBudgetRequest(BaseModel):
    month: date
    budgets: list[CategoryBudgetItem]
