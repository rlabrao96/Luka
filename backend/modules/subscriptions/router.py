from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from . import service
from .schemas import SubscriptionsResponse, SubscriptionOverrideRequest

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("/detected", response_model=SubscriptionsResponse)
async def detected_subscriptions(
    months_back: int = Query(default=6, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_detected_subscriptions(db, current_user.id, months_back)


@router.put("/override")
async def upsert_override(
    body: SubscriptionOverrideRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # If the caller set split_type, go through the reclassify service so
    # the change cascades to the last 3 months of transaction_splits and
    # the detected_subscriptions_cache gets invalidated in one atomic
    # operation. reclassify also upserts the override row, so we don't
    # call upsert_override separately in that branch.
    if body.split_type is not None:
        await service.reclassify_subscription_split(
            db,
            user_id=current_user.id,
            merchant_key=body.merchant_key,
            new_split_type=body.split_type,
            window_months=3,
        )
        # If the request ALSO carries other override fields (status,
        # category, next_charge_day), apply them via upsert_override so
        # they don't get lost.
        if body.status is not None or body.category is not None or body.next_charge_day is not None:
            await service.upsert_override(
                db,
                current_user.id,
                body.merchant_key,
                body.status,
                body.category,
                body.next_charge_day,
                split_type=None,  # already applied above
            )
    else:
        await service.upsert_override(
            db,
            current_user.id,
            body.merchant_key,
            body.status,
            body.category,
            body.next_charge_day,
            split_type=None,
        )
    return {"ok": True}


@router.post("/refresh", response_model=SubscriptionsResponse)
async def refresh_subscriptions(
    months_back: int = Query(default=6, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.refresh_subscriptions(db, current_user.id, months_back)
