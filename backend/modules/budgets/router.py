import uuid
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.budgets import service
from modules.budgets.schemas import (
    AllocationBlock,
    AllocationResponse,
    BudgetStatusResponse,
    PersonalBudgetResponse,
    SetAllocationRequest,
    SetBudgetRequest,
)
from modules.budgets.personal_service import get_personal_budget
from modules.budgets.allocation_service import get_allocation, upsert_allocation
from modules.households.auth import require_membership

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("/monthly/{household_id}", response_model=BudgetStatusResponse)
async def monthly_budget(
    household_id: uuid.UUID,
    month: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    if not month:
        today = date.today()
        month = date(today.year, today.month, 1)
    return await service.get_budget_status(db, household_id, month)


@router.post("/monthly/{household_id}", response_model=BudgetStatusResponse)
async def set_budget(
    household_id: uuid.UUID,
    body: SetBudgetRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    await service.set_monthly_budget(
        db, household_id, body.bank_account_id, body.month, body.amount
    )
    # Return current budget status after upsert
    return await service.get_budget_status(db, household_id, body.month)


@router.get("/personal/{household_id}", response_model=PersonalBudgetResponse)
async def personal_budget(
    household_id: uuid.UUID,
    month: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    if not month:
        today = date.today()
        month = date(today.year, today.month, 1)
    else:
        month = date(month.year, month.month, 1)
    return await get_personal_budget(db, household_id, current_user.id, month)


@router.get("/allocation/{household_id}", response_model=AllocationResponse)
async def get_budget_allocation(
    household_id: uuid.UUID,
    month: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    if not month:
        today = date.today()
        month = date(today.year, today.month, 1)
    else:
        month = date(month.year, month.month, 1)
    return await get_allocation(db, household_id, month)


@router.post("/allocation/{household_id}", response_model=AllocationBlock)
async def set_budget_allocation(
    household_id: uuid.UUID,
    body: SetAllocationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    month = date(body.month.year, body.month.month, 1)
    return await upsert_allocation(
        db, household_id, month, body.hogar_pct, body.ahorro_pct, body.personal_pct
    )
