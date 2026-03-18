import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from core.config import settings
from modules.auth.models import User
from core.database import AsyncSessionLocal
from sqlalchemy import select

bearer_scheme = HTTPBearer()

_supabase_client = None


def _get_supabase():
    global _supabase_client
    if _supabase_client is None:
        from supabase import create_client

        _supabase_client = create_client(settings.supabase_url, settings.supabase_anon_key)
    return _supabase_client


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> User:
    token = credentials.credentials
    try:
        supabase = _get_supabase()
        user_response = supabase.auth.get_user(token)
        supabase_user = user_response.user
        if not supabase_user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == supabase_user.email))
        user = result.scalar_one_or_none()
        if not user:
            # Auto-provision user row on first authenticated request (post-OAuth signup)
            meta = supabase_user.user_metadata or {}
            provider = (supabase_user.app_metadata or {}).get("provider", "google")
            email_provider = "outlook" if provider in ("azure", "microsoft") else "gmail"
            full_name = (
                meta.get("full_name") or meta.get("name") or supabase_user.email.split("@")[0]
            )
            user = User(
                id=uuid.UUID(supabase_user.id),
                email=supabase_user.email,
                full_name=full_name,
                email_provider=email_provider,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
    return user
