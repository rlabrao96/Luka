import logging
import re
import secrets
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import cache_delete, cache_get, cache_set
from core.database import get_db
from core.encryption import decrypt_token, encrypt_token
from core.security import (
    cached_membership,
    get_current_user,
    get_current_user_attached,
    invalidate_user_cache,
    load_membership,
    user_cache_key,
)
from modules.auth.models import User
from modules.auth.schemas import (
    ALLOWED_CURRENCIES,
    SendWhatsAppPinRequest,
    StoreProviderTokensRequest,
    UpdateProfileRequest,
    UserResponse,
    WhatsAppVerifyRequest,
)
from modules.email.factory import get_email_provider
from modules.currencies.service import sync_preferred_currency
from modules.whatsapp.sender import send_verification_pin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_response(current_user: User, membership: dict | None) -> UserResponse:
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        email_provider=current_user.email_provider,
        whatsapp_verified=current_user.whatsapp_verified,
        phone_whatsapp=current_user.phone_whatsapp,
        preferred_currency=current_user.preferred_currency,
        household_id=membership.get("household_id") if membership else None,
        contribution_mode=membership.get("contribution_mode") if membership else None,
        fixed_contribution_amount=(
            membership.get("fixed_contribution_amount") if membership else None
        ),
        fixed_contribution_currency=(
            membership.get("fixed_contribution_currency") if membership else None
        ),
        feature_trips_enabled=bool(current_user.feature_trips_enabled),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Serve from the user-cache blob when available — zero DB queries on hit.
    cached = await cache_get(user_cache_key(current_user.email))
    membership = cached_membership(cached)
    if cached is None:
        # Cache was populated in get_current_user for new blobs; for legacy
        # blobs without the `membership` field, backfill once.
        membership = await load_membership(db, current_user.id)
    return _user_response(current_user, membership)


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest,
    user: User = Depends(get_current_user_attached),
    db: AsyncSession = Depends(get_db),
):
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.phone_whatsapp is not None:
        normalized = re.sub(r"[\s\-()]", "", body.phone_whatsapp)
        if not re.fullmatch(r"\+\d{7,15}", normalized):
            raise HTTPException(status_code=422, detail="Número de WhatsApp inválido")
        user.phone_whatsapp = normalized
    if body.preferred_currency is not None:
        if body.preferred_currency not in ALLOWED_CURRENCIES:
            raise HTTPException(status_code=422, detail="Moneda no soportada")
        user.preferred_currency = body.preferred_currency
        # Sync user_currencies BEFORE commit — both changes land in one transaction
        await sync_preferred_currency(db, user.id, body.preferred_currency)
    await db.commit()
    await db.refresh(user)
    await invalidate_user_cache(user.email)

    membership = await load_membership(db, user.id)
    return _user_response(user, membership)


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


async def _verify_google_token_ownership(token: str, expected_email: str) -> None:
    """Call Google's tokeninfo endpoint and fail if the token was not issued
    for this Luka user. Prevents a compromised session from planting an
    attacker-controlled Gmail ingest source on a legitimate account."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"access_token": token},
            )
    except httpx.HTTPError as e:
        logger.warning("Google tokeninfo lookup failed: %s", e)
        raise HTTPException(status_code=502, detail="Unable to verify provider token")

    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Invalid or expired provider token")

    info = resp.json()
    token_email = (info.get("email") or "").lower()
    if not token_email or token_email != expected_email.lower():
        raise HTTPException(
            status_code=403,
            detail="Provider token does not belong to the current user",
        )


@router.post("/store-provider-tokens")
async def store_provider_tokens(
    body: StoreProviderTokensRequest,
    user: User = Depends(get_current_user_attached),
    db: AsyncSession = Depends(get_db),
):
    await _verify_google_token_ownership(body.provider_token, user.email)

    user.google_access_token_enc = encrypt_token(body.provider_token)
    if body.provider_refresh_token is not None:
        user.google_refresh_token_enc = encrypt_token(body.provider_refresh_token)

    await db.commit()
    await db.refresh(user)
    await invalidate_user_cache(user.email)

    return {"status": "ok"}


@router.post("/setup-email-watch")
async def setup_email_watch(
    user: User = Depends(get_current_user_attached),
    db: AsyncSession = Depends(get_db),
):
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
    await invalidate_user_cache(user.email)

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

    # Rate limit: 3 sends per hour per (user, phone). WhatsApp sends cost
    # money and each send overwrites the pending PIN (denial-of-verification).
    rl_key = f"whatsapp_pin_rl:{current_user.id}:{body.phone}"
    sends = await cache_get(rl_key) or {"count": 0}
    if sends["count"] >= 3:
        raise HTTPException(
            status_code=429,
            detail="Demasiados intentos. Espera una hora e intenta de nuevo.",
        )
    await cache_set(rl_key, {"count": sends["count"] + 1}, ttl_seconds=3600)

    pin = f"{secrets.randbelow(1_000_000):06d}"
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
    user = await db.merge(current_user, load=False)
    user.phone_whatsapp = body.phone
    user.whatsapp_verified = True
    await db.commit()
    await db.refresh(user)
    await invalidate_user_cache(user.email)
    await cache_delete(key)

    return {"status": "ok"}
