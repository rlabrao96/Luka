import hashlib
import logging
import time
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
from modules.households.models import HouseholdMember

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer()

# Asymmetric algorithms — verified via JWKS public keys (post-migration default).
# HS256 is NEVER accepted here to prevent algorithm-confusion attacks where an
# attacker signs a forged token using the public key as the HMAC secret.
_ASYMMETRIC_ALGS = ["ES256", "RS256"]

_jwks_client: PyJWKClient | None = None

_USER_CACHE_TTL = 300  # 5 min
_JWT_CACHE_TTL_MAX = 3600  # 1 h (supabase access-token lifetime cap)
_JWT_CACHE_TTL_MIN = 60


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=3600)
    return _jwks_client


def _decode_token(token: str) -> dict:
    signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
    return pyjwt.decode(
        token,
        signing_key.key,
        algorithms=_ASYMMETRIC_ALGS,
        audience="authenticated",
    )


def _token_cache_key(token: str) -> str:
    # sha256-truncated to keep the Redis key short without meaningfully
    # weakening collision resistance (2^64 search space).
    return f"jwt:{hashlib.sha256(token.encode()).hexdigest()[:16]}"


def user_cache_key(email: str) -> str:
    # v2: blob now includes the `membership` sub-object. Bumping the prefix
    # forces any v1 entry to be treated as a miss so /auth/me doesn't
    # briefly return household_id=null during the cache migration window.
    return f"user:v2:{email}"


async def invalidate_user_cache(email: str) -> None:
    """Drop the cached User+household blob. Call after any mutation that
    changes fields the cache holds (profile, household membership, role,
    contribution mode)."""
    await cache_delete(user_cache_key(email))


async def _verify_token(token: str) -> dict:
    """Verify a Supabase JWT, caching the decoded payload by token hash.

    JWKS verification is CPU-bound elliptic-curve work; caching the result
    keyed by `sha256(token)` skips that cost on every subsequent request
    during the token's lifetime. TTL is bounded by the token's own `exp`.
    """
    cache_key = _token_cache_key(token)
    cached = await cache_get(cache_key)
    if cached:
        return cached

    payload = _decode_token(token)
    exp = payload.get("exp")
    now = int(time.time())
    if exp:
        ttl = max(_JWT_CACHE_TTL_MIN, min(_JWT_CACHE_TTL_MAX, exp - now))
    else:
        ttl = _JWT_CACHE_TTL_MAX
    await cache_set(cache_key, payload, ttl_seconds=ttl)
    return payload


async def load_membership(db: AsyncSession, user_id: uuid.UUID) -> dict | None:
    result = await db.execute(
        select(
            HouseholdMember.household_id,
            HouseholdMember.contribution_mode,
            HouseholdMember.fixed_contribution_amount,
            HouseholdMember.fixed_contribution_currency,
        ).where(
            HouseholdMember.user_id == user_id,
            HouseholdMember.left_at.is_(None),
        )
    )
    row = result.first()
    if not row:
        return None
    return {
        "household_id": str(row[0]) if row[0] else None,
        "contribution_mode": row[1],
        "fixed_contribution_amount": str(row[2]) if row[2] is not None else None,
        "fixed_contribution_currency": row[3],
    }


def _build_cache_blob(user: User, membership: dict | None) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "email_provider": user.email_provider,
        "whatsapp_verified": user.whatsapp_verified,
        "phone_whatsapp": user.phone_whatsapp,
        "preferred_currency": user.preferred_currency,
        "membership": membership,
    }


def _user_from_cache(cached: dict) -> User:
    return User(
        id=uuid.UUID(cached["id"]),
        email=cached["email"],
        full_name=cached["full_name"],
        email_provider=cached["email_provider"],
        whatsapp_verified=cached.get("whatsapp_verified", False),
        phone_whatsapp=cached.get("phone_whatsapp"),
        preferred_currency=cached.get("preferred_currency", "CLP"),
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate Supabase JWT via JWKS (ES256/RS256) and return the User.

    Hot path: cached JWT payload + cached User blob → zero DB queries, zero
    JWKS work. The User returned here is detached from `db`; endpoints that
    mutate it should depend on `get_current_user_attached` instead.
    """
    token = credentials.credentials

    try:
        payload = await _verify_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    email = payload.get("email")
    sub = payload.get("sub")
    if not email or not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token claims")

    cache_key = user_cache_key(email)
    cached = await cache_get(cache_key)
    if cached:
        # Invalidate on identity change (account deleted + recreated)
        if cached["id"] != sub:
            await cache_delete(cache_key)
        else:
            return _user_from_cache(cached)

    # Cache miss — hit DB for the User row and (separately) the membership row.
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        # Auto-provision on first authenticated request (post-OAuth signup).
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

    membership = await load_membership(db, user.id)
    await cache_set(cache_key, _build_cache_blob(user, membership), ttl_seconds=_USER_CACHE_TTL)

    return user


async def get_current_user_attached(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Return a session-bound User for endpoints that mutate it.

    On cache hit `current_user` is a detached ORM instance; merge(load=False)
    attaches it to the session as persistent without issuing any SELECT.
    When `current_user` was auto-provisioned (miss path) it is already bound,
    and merge is a no-op for an attached instance.
    """
    return await db.merge(current_user, load=False)


def cached_membership(cached: dict | None) -> dict | None:
    """Extract the membership sub-blob from a cache_get(user:*) result."""
    if not cached:
        return None
    return cached.get("membership")
