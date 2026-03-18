from fastapi import APIRouter, Depends
from sqlalchemy import select
from core.database import AsyncSessionLocal
from core.security import get_current_user
from modules.auth.models import User
from modules.auth.schemas import UserResponse
from modules.households.models import HouseholdMember

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(HouseholdMember.household_id).where(HouseholdMember.user_id == current_user.id)
        )
        row = result.first()
        household_id = row[0] if row else None

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        email_provider=current_user.email_provider,
        whatsapp_verified=current_user.whatsapp_verified,
        household_id=household_id,
    )
