import uuid
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from modules.households.models import HouseholdMember

router = APIRouter(prefix="/bank-accounts", tags=["bank-accounts"])


async def _require_household_membership(
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
