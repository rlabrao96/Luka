import logging
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import cache_get, cache_set
from core.config import settings
from core.database import get_db
from modules.auth.models import User

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate Supabase JWT locally (no external API call) and return the User.

    Uses the shared DB session from get_db so routes don't open multiple connections.
    Auto-provisions a user row on first authenticated request (post-OAuth signup).
    """
    token = credentials.credentials

    # Decode JWT locally — no network call, ~0ms
    # Accept both HS256 and RS256 (Supabase uses HS256 by default)
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256", "RS256"],
            audience="authenticated",
        )
    except JWTError as e:
        logger.warning("JWT validation failed: %s", e)

        # Fallback: if local JWT validation fails (e.g. missing/wrong secret),
        # use the Supabase SDK to validate against the server.
        try:
            from supabase import create_client

            sb = create_client(settings.supabase_url, settings.supabase_anon_key)
            user_response = sb.auth.get_user(token)
            su = user_response.user
            if not su:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
            payload = {
                "email": su.email,
                "sub": su.id,
                "user_metadata": su.user_metadata or {},
                "app_metadata": su.app_metadata or {},
            }
        except HTTPException:
            raise
        except Exception as e2:
            logger.exception("Supabase fallback auth also failed: %s", e2)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    email = payload.get("email")
    sub = payload.get("sub")
    if not email or not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token claims")

    # Check Redis cache first (avoids DB hit on every request)
    cache_key = f"user:{email}"
    cached = await cache_get(cache_key)
    if cached:
        return User(
            id=uuid.UUID(cached["id"]),
            email=cached["email"],
            full_name=cached["full_name"],
            email_provider=cached["email_provider"],
            whatsapp_verified=cached.get("whatsapp_verified", False),
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
        },
        ttl_seconds=300,
    )

    return user
