"""GET / PATCH /settings/budget — savings target + payday day-of-month.

Thin layer over `user_budget_settings_service`. Mounted in `main.py`.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from modules.auth.schemas import ALLOWED_CURRENCIES
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.budgets.user_budget_settings_models import UserBudgetSettings
from modules.budgets.user_budget_settings_service import (
    get_or_create,
    update_payday,
    update_personal_allocation,
    update_savings_target,
)

router = APIRouter(prefix="/settings/budget", tags=["settings"])


_AMOUNT_BOUNDS = {"ge": 0, "le": 1_000_000_000}


class BudgetSettingsRequest(BaseModel):
    savings_target_amount: Decimal | None = Field(default=None, **_AMOUNT_BOUNDS)
    savings_target_currency: str | None = Field(default=None, min_length=3, max_length=3)
    payday_day_of_month: int | None = None
    personal_allocation_amount: Decimal | None = Field(default=None, **_AMOUNT_BOUNDS)
    personal_allocation_currency: str | None = Field(default=None, min_length=3, max_length=3)

    @field_validator("savings_target_currency", "personal_allocation_currency")
    @classmethod
    def _validate_currency(cls, v: str | None) -> str | None:
        if v is None:
            return None
        code = v.upper()
        if code not in ALLOWED_CURRENCIES:
            raise ValueError(f"unsupported currency: {v}")
        return code


class BudgetSettingsResponse(BaseModel):
    savings_target_amount: Decimal | None
    savings_target_currency: str | None
    payday_day_of_month: int | None
    personal_allocation_amount: Decimal | None
    personal_allocation_currency: str | None


@router.get("", response_model=BudgetSettingsResponse)
async def get_budget_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Read-only: don't insert an empty user_budget_settings row on first read.
    # The PATCH path creates the row via get_or_create when the user actually
    # saves something. TanStack Query hits this often (page load / refocus);
    # creating a row each time was write-amplification with no benefit.
    res = await db.execute(
        select(UserBudgetSettings).where(UserBudgetSettings.user_id == current_user.id)
    )
    row = res.scalar_one_or_none()
    if row is None:
        return BudgetSettingsResponse(
            savings_target_amount=None,
            savings_target_currency=None,
            payday_day_of_month=None,
            personal_allocation_amount=None,
            personal_allocation_currency=None,
        )
    return BudgetSettingsResponse(
        savings_target_amount=row.savings_target_amount,
        savings_target_currency=row.savings_target_currency,
        payday_day_of_month=row.payday_day_of_month,
        personal_allocation_amount=row.personal_allocation_amount,
        personal_allocation_currency=row.personal_allocation_currency,
    )


@router.patch("", response_model=BudgetSettingsResponse)
async def patch_budget_settings(
    payload: BudgetSettingsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Use model_fields_set so we can distinguish "field omitted" from
    # "field explicitly sent as null". `null` means "clear this value" —
    # checking `is not None` would lose that semantic and silently ignore
    # clear operations from the UI.
    provided = payload.model_fields_set
    if "savings_target_amount" in provided or "savings_target_currency" in provided:
        await update_savings_target(
            db,
            user_id=current_user.id,
            amount=payload.savings_target_amount,
            currency=payload.savings_target_currency,
        )
    if "payday_day_of_month" in provided:
        try:
            await update_payday(db, user_id=current_user.id, day=payload.payday_day_of_month)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
    if "personal_allocation_amount" in provided or "personal_allocation_currency" in provided:
        await update_personal_allocation(
            db,
            user_id=current_user.id,
            amount=payload.personal_allocation_amount,
            currency=payload.personal_allocation_currency,
        )
    await db.commit()
    row = await get_or_create(db, user_id=current_user.id)
    return BudgetSettingsResponse(
        savings_target_amount=row.savings_target_amount,
        savings_target_currency=row.savings_target_currency,
        payday_day_of_month=row.payday_day_of_month,
        personal_allocation_amount=row.personal_allocation_amount,
        personal_allocation_currency=row.personal_allocation_currency,
    )
