import httpx
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from jobs.queue import enqueue_job
from modules.auth.models import User
from modules.fintoc.client import FintocClient
from modules.households.models import BankAccount
from modules.households.router import _require_membership

router = APIRouter(prefix="/bank-accounts", tags=["bank-accounts"])


@router.get("/fintoc/accounts")
async def get_fintoc_accounts(
    link_token: str,
    current_user: User = Depends(get_current_user),
):
    """Fetch available accounts for a Fintoc link token. Called after widget success."""
    client = FintocClient(link_token=link_token)
    try:
        accounts = await client.fetch_accounts()
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=400, detail="Failed to fetch accounts from Fintoc")
    return accounts


class FintocAccountIn(BaseModel):
    fintoc_account_id: str
    label: str  # "personal" | "partner" | "joint"


class ConnectFintocRequest(BaseModel):
    link_token: str
    household_id: uuid.UUID
    accounts: list[FintocAccountIn]


@router.post("/fintoc/connect")
async def connect_fintoc_accounts(
    body: ConnectFintocRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Store Fintoc-connected accounts and enqueue 90-day history import per account."""
    await _require_membership(body.household_id, current_user.id, db)

    # Check for duplicates before creating anything
    for acct in body.accounts:
        existing = await db.scalar(
            select(BankAccount).where(BankAccount.fintoc_account_id == acct.fintoc_account_id)
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Account {acct.fintoc_account_id} is already connected",
            )

    # Create and enqueue
    created = []
    for acct in body.accounts:
        bank_account = BankAccount(
            household_id=body.household_id,
            user_id=current_user.id,
            bank_name="fintoc",
            account_type=acct.label,
            fintoc_link_id=body.link_token,
            fintoc_account_id=acct.fintoc_account_id,
            import_status="pending",
        )
        db.add(bank_account)
        await db.flush()
        created.append(bank_account)
        await enqueue_job("import_fintoc_history", bank_account_id=str(bank_account.id))

    await db.commit()
    return {
        "created": len(created),
        "accounts": [
            {
                "id": str(a.id),
                "fintoc_account_id": a.fintoc_account_id,
                "account_type": a.account_type,
            }
            for a in created
        ],
    }


@router.get("/import-status")
async def get_import_status(
    household_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Poll whether any account in this household is still importing history."""
    await _require_membership(household_id, current_user.id, db)

    result = await db.execute(
        select(BankAccount).where(
            BankAccount.household_id == household_id,
            BankAccount.import_status.in_(["pending", "importing"]),
        )
    )
    importing = result.scalars().first() is not None
    return {"importing": importing}
