import uuid
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.budgets import service
from modules.budgets.schemas import (
    BudgetStatusResponse,
    CategoryBudgetResponse,
    SetBudgetRequest,
    SetCategoryBudgetRequest,
)
from modules.budgets.category_service import get_category_budgets, set_category_budgets
from modules.budgets.v2_schemas import BudgetV2Response, DrilldownBlock
from modules.budgets.v2_service import get_budget_v2, get_node_drilldown
from modules.households.auth import require_membership

router = APIRouter(prefix="/budgets", tags=["budgets"])


def _normalize_month(m: date | None) -> date:
    if m is None:
        today = date.today()
        return date(today.year, today.month, 1)
    return date(m.year, m.month, 1)


@router.get("/monthly/{household_id}", response_model=BudgetStatusResponse)
async def monthly_budget(
    household_id: uuid.UUID,
    month: date | None = None,
    currency: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    return await service.get_budget_status(
        db, household_id, _normalize_month(month), currency=currency
    )


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
    return await service.get_budget_status(db, household_id, body.month)


@router.get("/categories/{household_id}", response_model=CategoryBudgetResponse)
async def get_cat_budgets(
    household_id: uuid.UUID,
    month: date | None = None,
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    return await get_category_budgets(db, household_id, _normalize_month(month), currency=currency)


@router.post("/categories/{household_id}", response_model=CategoryBudgetResponse)
async def set_cat_budgets(
    household_id: uuid.UUID,
    body: SetCategoryBudgetRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    month = date(body.month.year, body.month.month, 1)
    return await set_category_budgets(
        db, household_id, month, [b.model_dump() for b in body.budgets]
    )


@router.get("/v2/{household_id}", response_model=BudgetV2Response)
async def budget_v2(
    household_id: uuid.UUID,
    month: date | None = Query(default=None),
    currency: str | None = Query(default=None),
    view: str = Query(default="personal", pattern="^(personal|household)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    return await get_budget_v2(
        db,
        household_id=household_id,
        user_id=current_user.id,
        month=_normalize_month(month),
        currency=currency,
        view=view,
    )


@router.get("/v2/{household_id}/drilldown", response_model=DrilldownBlock)
async def budget_v2_drilldown(
    household_id: uuid.UUID,
    node_id: str = Query(..., min_length=1, max_length=120),
    view: str = Query(default="personal", pattern="^(personal|household)$"),
    month: date | None = Query(default=None),
    currency: str | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=25),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Top-N transactions for a clicked Sankey node. See
    `v2_service.get_node_drilldown` for the node-id dispatch table."""
    await require_membership(household_id, current_user.id, db)
    return await get_node_drilldown(
        db,
        household_id=household_id,
        user_id=current_user.id,
        month=_normalize_month(month),
        currency=currency,
        view=view,
        node_id=node_id,
        limit=limit,
    )
