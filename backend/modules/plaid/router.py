import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.encryption import decrypt_token, encrypt_token
from core.security import get_current_user
from jobs.queue import enqueue_job
from modules.plaid.models import PlaidItem
from modules.plaid.service import (
    create_link_token,
    exchange_public_token,
    remove_item,
)
from modules.households.models import BankAccount, HouseholdMember

router = APIRouter(prefix="/plaid", tags=["plaid"])


class ExchangeTokenRequest(BaseModel):
    public_token: str
    institution_id: str
    institution_name: str


@router.post("/create-link-token")
async def create_link_token_endpoint(
    user=Depends(get_current_user),
):
    try:
        token = create_link_token(user.id)
        return {"link_token": token}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create link token: {e}")


@router.post("/exchange-token")
async def exchange_token_endpoint(
    body: ExchangeTokenRequest,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    # Get user's household
    result = await session.execute(
        select(HouseholdMember.household_id).where(HouseholdMember.user_id == user.id)
    )
    household_id = result.scalar_one_or_none()
    if not household_id:
        raise HTTPException(status_code=400, detail="User has no household")

    try:
        access_token, item_id = exchange_public_token(body.public_token)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token exchange failed: {e}")

    # Create PlaidItem
    plaid_item = PlaidItem(
        user_id=user.id,
        household_id=household_id,
        plaid_item_id=item_id,
        access_token_enc=encrypt_token(access_token),
        institution_id=body.institution_id,
        institution_name=body.institution_name,
    )
    session.add(plaid_item)
    await session.flush()

    # Enqueue initial sync (90-day lookback)
    await enqueue_job("run_plaid_sync_job", plaid_item_id=str(plaid_item.id), initial=True)

    await session.commit()
    return {"plaid_item_id": str(plaid_item.id)}


@router.delete("/disconnect")
async def disconnect_endpoint(
    plaid_item_id: str,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(PlaidItem).where(
            PlaidItem.id == uuid.UUID(plaid_item_id),
            PlaidItem.user_id == user.id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Plaid item not found")

    # Remove from Plaid (stops billing)
    try:
        remove_item(decrypt_token(item.access_token_enc))
    except Exception:
        pass  # Best effort — item may already be removed

    # Soft-delete bank accounts (preserve transaction history)
    await session.execute(
        update(BankAccount).where(BankAccount.plaid_item_id == item.id).values(is_active=False)
    )

    # Delete PlaidItem
    await session.delete(item)
    await session.commit()

    return {"success": True}


@router.post("/sync")
async def manual_sync_endpoint(
    plaid_item_id: str,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(PlaidItem).where(
            PlaidItem.id == uuid.UUID(plaid_item_id),
            PlaidItem.user_id == user.id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Plaid item not found")

    await enqueue_job("run_plaid_sync_job", plaid_item_id=str(item.id), initial=False)

    return {"status": "syncing"}
