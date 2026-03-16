import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.transactions import service

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("/mine")
async def my_transactions(
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_my_transactions(db, current_user.id, limit=limit)


@router.get("/shared")
async def shared_transactions(
    household_id: uuid.UUID,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_shared_transactions(db, household_id, limit=limit)
