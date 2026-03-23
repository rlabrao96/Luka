from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.settings import service
from modules.settings.schemas import (
    CategoryPreferencesResponse,
    CategoryPreferencesUpdate,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
)

router = APIRouter(tags=["settings"])


@router.get("/notifications/preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pref = await service.get_notification_preferences(db, current_user.id)
    return pref


@router.patch("/notifications/preferences", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    body: NotificationPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pref = await service.update_notification_preferences(db, current_user.id, body.whatsapp_enabled)
    return pref


@router.get("/categories/preferences", response_model=CategoryPreferencesResponse)
async def get_category_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cats = await service.get_category_preferences(db, current_user.id)
    return CategoryPreferencesResponse(categories=cats)


@router.put("/categories/preferences", response_model=CategoryPreferencesResponse)
async def update_category_preferences(
    body: CategoryPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        cats = await service.update_category_preferences(
            db, current_user.id, [c.model_dump() for c in body.categories]
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return CategoryPreferencesResponse(categories=cats)
