import logging
import uuid

import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import cache_delete, cache_get, cache_set
from core.config import settings
from core.database import get_db
from modules.auth.models import User

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer()

# JWKS client fetches public keys from Supabase and caches them.
# Supports HS256, RS256, ES256 (ECC P-256) — whatever Supabase is configured to use.
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=3600)
    return _jwks_client


def _decode_token(token: str) -> dict:
    """Decode a Supabase JWT using JWKS (supports ES256, RS256, HS256).

    Tries JWKS first (asymmetric keys). Falls back to the legacy HS256
    shared secret if JWKS fails and SUPABASE_JWT_SECRET is configured.
    """
    # Strategy 1: JWKS endpoint (works for ES256/RS256 — current Supabase default)
    try:
        jwks_client = _get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        return pyjwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256", "HS256"],
            audience="authenticated",
        )
    except Exception as e:
        logger.debug("JWKS decode failed: %s", e)

    # Strategy 2: Legacy HS256 shared secret (if configured)
    if settings.supabase_jwt_secret:
        try:
            return pyjwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        except Exception as e:
            logger.debug("HS256 decode failed: %s", e)

    # Strategy 3: Supabase SDK server-side validation (slowest, always works)
    try:
        from supabase import create_client

        sb = create_client(settings.supabase_url, settings.supabase_anon_key)
        user_response = sb.auth.get_user(token)
        su = user_response.user
        if not su:
            raise ValueError("No user returned")
        return {
            "email": su.email,
            "sub": su.id,
            "user_metadata": su.user_metadata or {},
            "app_metadata": su.app_metadata or {},
        }
    except Exception as e:
        logger.warning("All JWT validation strategies failed: %s", e)
        raise


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate Supabase JWT and return the User.

    Uses JWKS for local validation (ES256/RS256), falls back to HS256 secret,
    then to Supabase SDK. Uses shared DB session from get_db.
    """
    token = credentials.credentials

    try:
        payload = _decode_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    email = payload.get("email")
    sub = payload.get("sub")
    if not email or not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token claims")

    # Check Redis cache first (avoids DB hit on every request)
    cache_key = f"user:{email}"
    cached = await cache_get(cache_key)
    if cached:
        # Invalidate cache if user ID changed (e.g., account deleted and re-created)
        if cached["id"] != sub:
            await cache_delete(cache_key)
        else:
            return User(
                id=uuid.UUID(cached["id"]),
                email=cached["email"],
                full_name=cached["full_name"],
                email_provider=cached["email_provider"],
                whatsapp_verified=cached.get("whatsapp_verified", False),
                phone_whatsapp=cached.get("phone_whatsapp"),
                preferred_currency=cached.get("preferred_currency", "CLP"),
            )

    # Cache miss — look up in DB (shared session, same as route handler)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        # Auto-provision user row on first authenticated request (post-OAuth signup)
        meta = payload.get("user_metadata", {})
        app_meta = payload.get("app_metadata", {})
        provider = app_meta.get("provider", "google")
        email_provider = "outlook" if provider in ("azure", "microsoft") else "gmail"
        full_name = meta.get("full_name") or meta.get("name") or email.split("@")[0]
        user = User(
            id=uuid.UUID(sub),
            email=email,
            full_name=full_name,
            email_provider=email_provider,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # Cache for 5 minutes
    await cache_set(
        cache_key,
        {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "email_provider": user.email_provider,
            "whatsapp_verified": user.whatsapp_verified,
            "phone_whatsapp": user.phone_whatsapp,
            "preferred_currency": user.preferred_currency,
        },
        ttl_seconds=300,
    )

    return user
