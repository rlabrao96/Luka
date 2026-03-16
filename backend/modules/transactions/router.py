import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.households.models import HouseholdMember
from modules.transactions import service
from modules.transactions.schemas import TransactionResponse

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("/mine", response_model=list[TransactionResponse])
async def my_transactions(
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_my_transactions(db, current_user.id, limit=limit)


@router.get("/shared", response_model=list[TransactionResponse])
async def shared_transactions(
    household_id: uuid.UUID,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify current user is a member of this household
    result = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.user_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this household")
    return await service.get_shared_transactions(db, household_id, limit=limit)
