from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from . import service
from .schemas import RecurringExpenseResponse

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("/detected", response_model=list[RecurringExpenseResponse])
async def detected_subscriptions(
    months_back: int = Query(default=6, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_detected_subscriptions(db, current_user.id, months_back)
