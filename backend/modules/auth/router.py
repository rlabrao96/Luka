from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.auth.schemas import UpdateProfileRequest, UserResponse
from modules.households.models import HouseholdMember

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
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
        phone_whatsapp=current_user.phone_whatsapp,
        household_id=household_id,
    )


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Re-fetch from DB session (current_user may be cached/detached)
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()

    if body.full_name is not None:
        user.full_name = body.full_name
    if body.phone_whatsapp is not None:
        user.phone_whatsapp = body.phone_whatsapp
    await db.commit()
    await db.refresh(user)

    result = await db.execute(
        select(HouseholdMember.household_id).where(HouseholdMember.user_id == user.id)
    )
    row = result.first()
    household_id = row[0] if row else None

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        email_provider=user.email_provider,
        whatsapp_verified=user.whatsapp_verified,
        phone_whatsapp=user.phone_whatsapp,
        household_id=household_id,
    )


@router.delete("/me", status_code=204)
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_confirm_delete: str = Header(None),
):
    if x_confirm_delete != "ELIMINAR":
        raise HTTPException(status_code=400, detail="Confirmation header missing or incorrect")

    from modules.settings.service import delete_user_account

    await delete_user_account(db, current_user.id)

    # Delete Supabase auth user (sync call — run in executor to avoid blocking)
    import asyncio

    from core.config import settings
    from supabase import create_client

    supabase_admin = create_client(settings.supabase_url, settings.supabase_service_key)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, supabase_admin.auth.admin.delete_user, str(current_user.id))
