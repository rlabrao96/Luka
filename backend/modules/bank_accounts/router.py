import httpx
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from jobs.queue import enqueue_job
from modules.auth.models import User
from modules.fintoc.client import FintocClient
from modules.households.models import BankAccount
from modules.households.auth import require_membership
from modules.transactions.models import Transaction, TransactionSplit

router = APIRouter(prefix="/bank-accounts", tags=["bank-accounts"])


@router.get("")
async def list_bank_accounts(
    household_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all connected bank accounts for a household."""
    await require_membership(household_id, current_user.id, db)

    result = await db.execute(
        select(BankAccount).where(
            BankAccount.household_id == household_id,
            BankAccount.is_active.is_(True),
        )
    )
    accounts = result.scalars().all()

    # Stale guard: if import has been "importing" for >15 min, write "failed" to DB
    stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
    for a in accounts:
        if (
            a.import_status == "importing"
            and a.import_started_at
            and a.import_started_at < stale_cutoff
        ):
            a.import_status = "failed"
    if any(a.import_status == "failed" for a in accounts):
        await db.commit()

    return [
        {
            "id": str(a.id),
            "bank_name": a.bank_name,
            "account_type": a.account_type,
            "account_kind": a.account_kind,
            "account_number": a.account_number,
            "cardholder_name": a.cardholder_name,
            "user_id": str(a.user_id),
            "import_status": a.import_status,
            "fintoc_account_id": a.fintoc_account_id,
            "last_synced_at": a.last_synced_at.isoformat() if a.last_synced_at else None,
        }
        for a in accounts
    ]


@router.get("/fintoc/accounts")
async def get_fintoc_accounts(
    link_token: str,
    current_user: User = Depends(get_current_user),
):
    """Fetch available accounts for a Fintoc link token. Called after widget success."""
    client = FintocClient(link_token=link_token)
    try:
        accounts = await client.fetch_accounts()
    except (httpx.HTTPStatusError, httpx.RequestError):
        raise HTTPException(status_code=502, detail="Failed to fetch accounts from Fintoc")
    return accounts


class FintocAccountIn(BaseModel):
    fintoc_account_id: str
    label: str  # "personal" | "partner" | "joint"
    bank_name: str | None = None
    account_kind: str | None = None  # "checking_account" | "credit_card" | "savings_account"
    account_number: str | None = None


class ConnectFintocRequest(BaseModel):
    link_token: str
    household_id: uuid.UUID
    accounts: list[FintocAccountIn]


class UpdateBankAccountBody(BaseModel):
    account_type: Literal["personal", "partner", "joint"] | None = None
    is_active: bool | None = None


@router.post("/fintoc/connect")
async def connect_fintoc_accounts(
    body: ConnectFintocRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Store Fintoc-connected accounts and enqueue 90-day history import per account."""
    await require_membership(body.household_id, current_user.id, db)

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
            bank_name=acct.bank_name or "Fintoc",
            account_type=acct.label,
            account_kind=acct.account_kind,
            account_number=acct.account_number,
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
                "account_kind": a.account_kind,
                "bank_name": a.bank_name,
            }
            for a in created
        ],
    }


@router.patch("/{account_id}")
async def update_bank_account(
    account_id: uuid.UUID,
    household_id: uuid.UUID,
    body: UpdateBankAccountBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update account_type and/or is_active. Only the account owner can edit."""
    await require_membership(household_id, current_user.id, db)

    account = await db.scalar(
        select(BankAccount).where(
            BankAccount.id == account_id,
            BankAccount.household_id == household_id,
        )
    )
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the account owner can edit it")

    # Guard: cannot disable while import is in progress
    if body.is_active is False and account.import_status in ("pending", "importing"):
        raise HTTPException(
            status_code=409,
            detail="Cannot disable an account while its history import is in progress",
        )

    if body.account_type is not None:
        account.account_type = body.account_type
    if body.is_active is not None:
        account.is_active = body.is_active

    await db.commit()
    return {
        "id": str(account.id),
        "account_type": account.account_type,
        "is_active": account.is_active,
    }


@router.post("/webhooks/fintoc-link")
async def fintoc_link_webhook(
    request: Request,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Receive link.created webhook from Fintoc (sent via webhookUrl in widget config).
    Auto-creates BankAccount rows and enqueues 90-day history import per account.
    household_id and user_id are passed as query params in the webhookUrl.
    """
    body = await request.json()

    if body.get("type") != "link.created":
        return {"ok": True}

    data = body.get("data", {})
    link_token = data.get("link_token")
    accounts = data.get("accounts") or []
    institution = data.get("institution") or {}
    bank_name = institution.get("name", "Fintoc")

    if not link_token:
        raise HTTPException(status_code=400, detail="Missing link_token in event data")

    created = 0
    for acc in accounts:
        fintoc_account_id = acc.get("id")
        if not fintoc_account_id:
            continue
        existing = await db.scalar(
            select(BankAccount).where(BankAccount.fintoc_account_id == fintoc_account_id)
        )
        if existing:
            continue
        bank_account = BankAccount(
            household_id=household_id,
            user_id=user_id,
            bank_name=bank_name,
            account_type="personal",
            account_kind=acc.get("type"),
            account_number=acc.get("number"),
            fintoc_link_id=link_token,
            fintoc_account_id=fintoc_account_id,
            import_status="pending",
        )
        db.add(bank_account)
        await db.flush()
        await enqueue_job("import_fintoc_history", bank_account_id=str(bank_account.id))
        await db.commit()
        created += 1

    return {"ok": True, "created": created}


@router.delete("/{account_id}")
async def delete_bank_account(
    account_id: uuid.UUID,
    household_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hard-delete a bank account and all its transactions/splits. Only the account owner can delete."""
    await require_membership(household_id, current_user.id, db)

    account = await db.scalar(
        select(BankAccount).where(
            BankAccount.id == account_id,
            BankAccount.household_id == household_id,
        )
    )
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the account owner can disconnect it")

    # Delete splits → transactions → bank account (respect FK order)
    txn_ids_result = await db.execute(
        select(Transaction.id).where(Transaction.bank_account_id == account_id)
    )
    txn_ids = [row[0] for row in txn_ids_result.fetchall()]

    if txn_ids:
        await db.execute(
            delete(TransactionSplit).where(TransactionSplit.transaction_id.in_(txn_ids))
        )
        await db.execute(delete(Transaction).where(Transaction.id.in_(txn_ids)))

    await db.delete(account)
    await db.commit()
    return {"ok": True}


@router.get("/import-status")
async def get_import_status(
    household_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Poll whether any account in this household is still importing history."""
    await require_membership(household_id, current_user.id, db)

    result = await db.execute(
        select(BankAccount).where(
            BankAccount.household_id == household_id,
            BankAccount.import_status.in_(["pending", "importing"]),
        )
    )
    importing = result.scalars().first() is not None
    return {"importing": importing}
