import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.households.auth import require_membership
from modules.transactions import service
from modules.transactions.schemas import TransactionResponse, CategoryUpdateRequest

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("/mine", response_model=list[TransactionResponse])
async def my_transactions(
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_my_transactions(db, current_user.id, limit=limit)


@router.get("/monthly-summary")
async def monthly_summary(
    household_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    return await service.get_monthly_summary(db, household_id, current_user.id)


@router.get("/shared", response_model=list[TransactionResponse])
async def shared_transactions(
    household_id: uuid.UUID,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    return await service.get_shared_transactions(db, household_id, limit=limit)


@router.patch("/{transaction_id}/category")
async def update_category(
    transaction_id: uuid.UUID,
    body: CategoryUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    found = await service.update_category(db, transaction_id, current_user.id, body.category)
    if not found:
        raise HTTPException(404, "Transaction not found")
    return {"ok": True}
