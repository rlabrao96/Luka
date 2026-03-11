from fastapi import APIRouter, Depends
from core.security import get_current_user
from modules.auth.models import User
from modules.auth.schemas import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
