from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.settings import service
from modules.settings.schemas import (
    CategoryAddRequest,
    CategoryDeleteRequest,
    CategoryPreferenceItem,
    CategoryPreferencesResponse,
    CategoryReorderRequest,
    CategoryUsageResponse,
    HouseholdCategoryAdoptRequest,
    HouseholdCategoryAdoptResponse,
    HouseholdPartnerCategoriesResponse,
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
async def reorder_category_preferences(
    body: CategoryReorderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        cats = await service.reorder_categories(
            db, current_user.id, [c.model_dump() for c in body.categories]
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return CategoryPreferencesResponse(categories=cats)


@router.post("/categories/preferences", response_model=CategoryPreferenceItem, status_code=201)
async def add_category_preference(
    body: CategoryAddRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        cat = await service.add_category(db, current_user.id, body.category, body.category_type)
    except ValueError as e:
        msg = str(e)
        status = 409 if "Duplicate" in msg else 422
        raise HTTPException(status_code=status, detail=msg)
    return cat


@router.get("/categories/preferences/{category}/usage", response_model=CategoryUsageResponse)
async def get_category_usage(
    category: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count = await service.get_category_usage(db, current_user.id, category)
    return CategoryUsageResponse(count=count)


@router.get("/settings/household-categories", response_model=HouseholdPartnerCategoriesResponse)
async def get_household_partner_categories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cats = await service.get_household_partner_categories(db, current_user.id)
    return HouseholdPartnerCategoriesResponse(categories=cats)


@router.post(
    "/settings/household-categories/adopt",
    response_model=HouseholdCategoryAdoptResponse,
)
async def adopt_household_category(
    body: HouseholdCategoryAdoptRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await service.adopt_household_category(
            db, current_user.id, body.category, body.category_type
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return result


@router.post("/categories/preferences/{category}/delete", status_code=200)
async def delete_category_preference(
    category: str,
    body: CategoryDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await service.delete_category(db, current_user.id, category, body.reclassify_to)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"ok": True}
