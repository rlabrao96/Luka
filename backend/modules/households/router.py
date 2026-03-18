import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.households import service
from modules.households.models import Household, HouseholdMember
from modules.households.schemas import CreateHouseholdRequest, HouseholdResponse, InviteRequest

# Two routers: one under /households, one at root for the invite accept link
router = APIRouter(prefix="/households", tags=["households"])
invite_router = APIRouter(tags=["households"])  # no prefix — produces /invite/{token}


async def _require_membership(
    household_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> None:
    """Raise 403 if user is not a member of the household."""
    result = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.user_id == user_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this household")


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
    # TODO Plan 2: enqueue invite email ARQ job
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
    await _require_membership(household_id, current_user.id, db)
    return await service.get_contribution_summary(db, household_id)


@router.get("/{household_id}/partner-stats")
async def partner_stats(
    household_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_membership(household_id, current_user.id, db)
    return await service.get_partner_stats(db, household_id, current_user.id)
