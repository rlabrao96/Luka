import random
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import cache_delete, cache_get, cache_set
from core.database import get_db
from core.encryption import decrypt_token, encrypt_token
from core.security import get_current_user
from modules.auth.models import User
from modules.auth.schemas import (
    SendWhatsAppPinRequest,
    StoreProviderTokensRequest,
    UpdateProfileRequest,
    UserResponse,
    WhatsAppVerifyRequest,
)
from modules.email.factory import get_email_provider
from modules.households.models import HouseholdMember
from modules.whatsapp.sender import send_verification_pin

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
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found. Please re-authenticate.")

    if body.full_name is not None:
        user.full_name = body.full_name
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


@router.post("/store-provider-tokens")
async def store_provider_tokens(
    body: StoreProviderTokensRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found. Please re-authenticate.")

    user.google_access_token_enc = encrypt_token(body.provider_token)
    if body.provider_refresh_token is not None:
        user.google_refresh_token_enc = encrypt_token(body.provider_refresh_token)

    await db.commit()
    await db.refresh(user)
    await cache_delete(f"user:{user.email}")

    return {"status": "ok"}


@router.post("/setup-email-watch")
async def setup_email_watch(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found. Please re-authenticate.")

    if not user.google_access_token_enc:
        raise HTTPException(
            status_code=400, detail="No Google tokens stored. Please re-authenticate."
        )

    access_token = decrypt_token(user.google_access_token_enc)
    refresh_token = (
        decrypt_token(user.google_refresh_token_enc) if user.google_refresh_token_enc else ""
    )

    provider = get_email_provider(user, access_token=access_token, refresh_token=refresh_token)
    watch_result = await provider.setup_watch(str(user.id))

    user.mail_watch_subscription_id = watch_result.get("subscription_id")
    expiry_ms = watch_result.get("expiry")
    if expiry_ms:
        user.mail_watch_expiry = datetime.fromtimestamp(int(expiry_ms) / 1000, tz=timezone.utc)

    # Persist refreshed token if changed
    new_token = provider.get_current_token()
    if new_token and new_token != access_token:
        user.google_access_token_enc = encrypt_token(new_token)

    await db.commit()
    await db.refresh(user)
    await cache_delete(f"user:{user.email}")

    return {
        "status": "ok",
        "expiry": str(user.mail_watch_expiry) if user.mail_watch_expiry else None,
    }


@router.post("/send-whatsapp-pin")
async def send_whatsapp_pin(
    body: SendWhatsAppPinRequest,
    current_user: User = Depends(get_current_user),
):
    if not re.fullmatch(r"\+\d{7,15}", body.phone):
        raise HTTPException(status_code=422, detail="Número inválido")

    pin = str(random.randint(100000, 999999))
    await cache_set(
        f"whatsapp_pin:{body.phone}",
        {"pin": pin, "user_id": str(current_user.id), "attempts": 0},
        ttl_seconds=300,
    )

    try:
        await send_verification_pin(body.phone, pin)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="No se pudo enviar el PIN. Intenta de nuevo.",
        )

    return {"status": "ok"}


@router.post("/verify-whatsapp-pin")
async def verify_whatsapp_pin(
    body: WhatsAppVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    key = f"whatsapp_pin:{body.phone}"
    data = await cache_get(key)

    if not data:
        raise HTTPException(status_code=400, detail="PIN incorrecto o expirado")

    if data["user_id"] != str(current_user.id):
        raise HTTPException(status_code=400, detail="PIN incorrecto o expirado")

    if data["pin"] != body.pin:
        data["attempts"] = data.get("attempts", 0) + 1
        if data["attempts"] >= 5:
            await cache_delete(key)
        else:
            await cache_set(key, data, ttl_seconds=300)
        raise HTTPException(status_code=400, detail="PIN incorrecto o expirado")

    # Success — save phone and mark verified
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found. Please re-authenticate.")
    user.phone_whatsapp = body.phone
    user.whatsapp_verified = True
    await db.commit()
    await db.refresh(user)
    await cache_delete(f"user:{user.email}")
    await cache_delete(key)

    return {"status": "ok"}
