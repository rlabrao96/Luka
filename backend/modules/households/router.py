import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.households import service
from modules.households.models import Household, HouseholdMember
from modules.households.schemas import (
    CreateHouseholdRequest,
    HouseholdResponse,
    InviteRequest,
    SettlementResponse,
    SplitRatioRequest,
    SplitRatioResponse,
)
from modules.households.auth import require_membership

# Two routers: one under /households, one at root for the invite accept link
router = APIRouter(prefix="/households", tags=["households"])
invite_router = APIRouter(tags=["households"])  # no prefix — produces /invite/{token}


@router.post("", response_model=HouseholdResponse)
async def create_household(
    body: CreateHouseholdRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.create_household(db, current_user, body.name, body.type)


@router.post("/{household_id}/invite")
async def invite_partner(
    household_id: uuid.UUID,
    body: InviteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Household).where(Household.id == household_id))
    household = result.scalar_one_or_none()
    if not household:
        raise HTTPException(404, "Household not found")
    member_result = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.user_id == current_user.id,
            HouseholdMember.role == "owner",
        )
    )
    if not member_result.scalar_one_or_none():
        raise HTTPException(403, "Only the household owner can invite members")
    invite = await service.create_invite(db, household, current_user, body.email)
    from jobs.queue import enqueue_job

    await enqueue_job(
        "send_invite_email",
        email_to=body.email,
        token=invite.token,
        inviter_name=current_user.full_name,
        household_name=household.name,
    )
    return {"token": invite.token, "expires_at": invite.expires_at}


@invite_router.get("/invite/{token}")
async def accept_invite(
    token: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Partner clicks this link from their invite email to join the household."""
    try:
        invite = await service.accept_invite(db, token, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"household_id": invite.household_id, "accepted_at": invite.accepted_at}


@router.get("/{household_id}/summary")
async def household_summary(
    household_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    return await service.get_contribution_summary(db, household_id)


@router.get("/{household_id}/partner-stats")
async def partner_stats(
    household_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    return await service.get_partner_stats(db, household_id, current_user.id)


@router.get("/{household_id}/category-breakdown")
async def category_breakdown(
    household_id: uuid.UUID,
    month: str = Query(default=None, description="YYYY-MM format"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    data = await service.get_category_breakdown(db, household_id, month)
    return data


@router.get("/{household_id}/settlement", response_model=SettlementResponse)
async def settlement(
    household_id: uuid.UUID,
    month: str = Query(default=None, description="YYYY-MM format"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    return await service.get_settlement(db, household_id, month)


@router.get("/{household_id}/split-ratio", response_model=SplitRatioResponse)
async def get_split_ratio(
    household_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    result = await db.execute(
        text("SELECT split_ratio FROM households WHERE id = :id"),
        {"id": str(household_id)},
    )
    ratio = result.scalar_one_or_none() or [50, 50]
    return {"split_ratio": ratio}


@router.patch("/{household_id}/split-ratio", response_model=SplitRatioResponse)
async def update_split_ratio(
    household_id: uuid.UUID,
    body: SplitRatioRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)

    # Validate: 2-5 elements, all non-negative, sum to 100
    if (
        len(body.ratio) < 2
        or len(body.ratio) > 5
        or sum(body.ratio) != 100
        or any(r < 0 for r in body.ratio)
    ):
        raise HTTPException(400, "Ratio must be 2-5 non-negative integers summing to 100")

    # Validate length matches active member count
    active_count_result = await db.execute(
        text("""
            SELECT COUNT(*) FROM household_members
            WHERE household_id = :hid AND left_at IS NULL
        """),
        {"hid": str(household_id)},
    )
    active_count = active_count_result.scalar()
    if len(body.ratio) != active_count:
        raise HTTPException(
            400, f"Ratio length ({len(body.ratio)}) must match active member count ({active_count})"
        )

    await db.execute(
        text("UPDATE households SET split_ratio = :ratio WHERE id = :id"),
        {"ratio": json.dumps(body.ratio), "id": str(household_id)},
    )
    await db.commit()
    return {"split_ratio": body.ratio}
