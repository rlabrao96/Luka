import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.merchant_review import service
from modules.merchant_review.schemas import (
    MerchantApproval,
    ReviewCardResponse,
    ReviewStatusResponse,
)

router = APIRouter(prefix="/merchant-review", tags=["merchant-review"])


@router.get("/{job_id}", response_model=list[ReviewCardResponse])
async def get_review_cards(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_review_cards(db, job_id, current_user.id)


@router.get("/{job_id}/status", response_model=ReviewStatusResponse)
async def get_review_status(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    status = await service.get_review_status(db, job_id, current_user.id)
    if not status:
        raise HTTPException(404, "Review job not found")
    return status


@router.patch("/{job_id}/merchants/{canonical_id}")
async def approve_merchant(
    job_id: uuid.UUID,
    canonical_id: uuid.UUID,
    body: MerchantApproval,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.action == "skip":
        return {"ok": True}

    ok = await service.approve_merchant(
        db, current_user.id, job_id, canonical_id, body.display_name, body.category
    )
    if not ok:
        raise HTTPException(404, "Merchant not found")
    return {"ok": True}


@router.post("/{job_id}/skip")
async def skip_review(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ok = await service.skip_review(db, current_user.id, job_id)
    if not ok:
        raise HTTPException(404, "Review job not found")
    return {"ok": True}
