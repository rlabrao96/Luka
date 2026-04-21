"""REST surface for cuotas (installment purchases).

- POST   /cuotas                  create a cuota (from a prefilled dialog)
- GET    /cuotas?scope=...        list active cuotas, scoped personal|household
- DELETE /cuotas/{id}             cancel a cuota (owner only)

Household-scoped operations require an explicit `household_id` so multi-
household users never have their data silently landed in the wrong group.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.budgets import cuota_service
from modules.budgets.cuota_schemas import (
    CuotaCreateRequest,
    CuotaListResponse,
    CuotaResponse,
)
from modules.households.auth import require_membership

router = APIRouter(prefix="/cuotas", tags=["cuotas"])


@router.post(
    "",
    response_model=CuotaResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_cuota(
    payload: CuotaCreateRequest,
    household_id: uuid.UUID = Query(..., description="Target household for this cuota"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CuotaResponse:
    await require_membership(household_id, current_user.id, db)
    try:
        cuota = await cuota_service.create_cuota(
            db,
            user_id=current_user.id,
            household_id=household_id,
            merchant_name=payload.merchant_name,
            total_amount=payload.total_amount,
            currency=payload.currency,
            installments_total=payload.installments_total,
            first_cuota_date=payload.first_cuota_date,
            split_type=payload.split_type,
            origin_transaction_id=payload.origin_transaction_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(cuota)
    return CuotaResponse.model_validate(cuota)


@router.get("", response_model=CuotaListResponse)
async def get_cuotas(
    scope: str = Query(default="personal", pattern="^(personal|household)$"),
    household_id: uuid.UUID | None = Query(
        default=None,
        description="Required when scope='household'",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CuotaListResponse:
    if scope == "personal":
        cuotas = await cuota_service.list_active_cuotas(
            db, scope="personal", user_id=current_user.id
        )
    else:
        if household_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="household_id is required when scope='household'",
            )
        await require_membership(household_id, current_user.id, db)
        cuotas = await cuota_service.list_active_cuotas(
            db, scope="household", household_id=household_id
        )
    return CuotaListResponse(cuotas=[CuotaResponse.model_validate(c) for c in cuotas])


@router.delete("/{cuota_id}")
async def delete_cuota(
    cuota_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, bool]:
    """Cancel a cuota. Returns {"ok": true} on success.

    Returns a JSON body (not 204) so the frontend's generic apiFetch wrapper
    — which unconditionally calls `res.json()` — doesn't throw on an empty
    response body. Matches the notifications/merchant-review DELETE idiom.
    """
    try:
        await cuota_service.cancel_cuota(db, cuota_id=cuota_id, user_id=current_user.id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="cuota not found"
        ) from exc
    await db.commit()
    return {"ok": True}
