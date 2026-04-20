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

# Asymmetric algorithms — verified via JWKS public keys (post-migration default).
# HS256 is NEVER accepted here to prevent algorithm-confusion attacks where an
# attacker signs a forged token using the public key as the HMAC secret.
_ASYMMETRIC_ALGS = ["ES256", "RS256"]

_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=3600)
    return _jwks_client


def _decode_token(token: str) -> dict:
    """Decode a Supabase JWT.

    Order of attempts:
      1. JWKS (asymmetric ES256/RS256 only) — Supabase's new default after
         the JWT Signing Keys migration. Rejects HS256 to block alg-confusion.
      2. Legacy HS256 shared secret — only used for tokens issued before the
         Dashboard rotation. Remove after the legacy key is revoked.
    """
    unverified_header = pyjwt.get_unverified_header(token)
    alg = unverified_header.get("alg")

    # Strategy 1: Asymmetric verification via JWKS (ES256/RS256).
    if alg in _ASYMMETRIC_ALGS:
        try:
            signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
            return pyjwt.decode(
                token,
                signing_key.key,
                algorithms=_ASYMMETRIC_ALGS,
                audience="authenticated",
            )
        except Exception as e:
            logger.warning("Asymmetric JWT decode failed (alg=%s): %s", alg, e)
            raise

    # Strategy 2: Legacy HS256 shared secret (pre-migration tokens only).
    if alg == "HS256" and settings.supabase_jwt_secret:
        try:
            return pyjwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        except Exception as e:
            logger.warning("Legacy HS256 decode failed: %s", e)
            raise

    raise pyjwt.InvalidTokenError(f"Unsupported or unverifiable JWT alg: {alg}")


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
