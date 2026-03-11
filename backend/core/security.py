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
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found. Complete onboarding.",
            )
    return user
