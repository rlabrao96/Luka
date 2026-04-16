# backend/modules/currencies/router.py
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.currencies import service
from modules.currencies.schemas import AddCurrencyBody, UserCurrencyOut

router = APIRouter(prefix="/currencies", tags=["currencies"])


@router.get("", response_model=list[UserCurrencyOut])
async def get_currencies(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_currencies(db, current_user.id)


@router.post("", response_model=UserCurrencyOut, status_code=201)
async def add_currency(
    body: AddCurrencyBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.add_currency(db, current_user.id, body.currency_code)
    except ValueError as e:
        msg = str(e)
        status = 409 if "Already" in msg else 400
        raise HTTPException(status_code=status, detail=msg)


@router.delete("/{currency_code}", status_code=204)
async def delete_currency(
    currency_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await service.delete_currency(db, current_user.id, currency_code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
