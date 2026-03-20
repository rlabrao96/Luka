import uuid
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.budgets import service
from modules.budgets.schemas import BudgetStatusResponse, SetBudgetRequest
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
