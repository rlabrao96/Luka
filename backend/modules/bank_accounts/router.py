import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
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
    """List all connected bank accounts for a household (active and inactive)."""
    await require_membership(household_id, current_user.id, db)

    result = await db.execute(
        select(BankAccount).where(
            BankAccount.household_id == household_id,
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
            "currency": a.currency,
            "is_active": a.is_active,
            "user_id": str(a.user_id),
            "import_status": a.import_status,
            "fintoc_account_id": a.fintoc_account_id,
            "last_synced_at": a.last_synced_at.isoformat() if a.last_synced_at else None,
            "balance_available": a.balance_available,
            "balance_current": a.balance_current,
        }
        for a in accounts
    ]


class CreateBankAccountBody(BaseModel):
    bank_name: str
    account_type: Literal["personal", "partner", "joint"]
    account_kind: Optional[str] = None
    account_number: Optional[str] = None
    cardholder_name: Optional[str] = None
    currency: Optional[str] = "CLP"
    household_id: uuid.UUID


@router.post("")
async def create_bank_account(
    body: CreateBankAccountBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually create a bank account for a household."""
    await require_membership(body.household_id, current_user.id, db)

    bank_account = BankAccount(
        household_id=body.household_id,
        user_id=current_user.id,
        bank_name=body.bank_name,
        account_type=body.account_type,
        account_kind=body.account_kind,
        account_number=body.account_number,
        cardholder_name=body.cardholder_name,
        currency=body.currency,
        import_status="done",
    )
    db.add(bank_account)
    await db.commit()
    await db.refresh(bank_account)
    return {
        "id": str(bank_account.id),
        "bank_name": bank_account.bank_name,
        "account_type": bank_account.account_type,
        "account_kind": bank_account.account_kind,
        "account_number": bank_account.account_number,
        "currency": bank_account.currency,
        "is_active": bank_account.is_active,
    }


class UpdateBankAccountBody(BaseModel):
    account_type: Literal["personal", "partner", "joint"] | None = None
    is_active: bool | None = None


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

    if body.account_type is not None and body.account_type != account.account_type:
        account.account_type = body.account_type
        # Backfill existing splits to match the new account type
        new_split_type = "shared" if body.account_type == "joint" else body.account_type
        txn_ids_result = await db.execute(
            select(Transaction.id).where(Transaction.bank_account_id == account_id)
        )
        txn_ids = [row[0] for row in txn_ids_result.fetchall()]
        if txn_ids:
            await db.execute(
                update(TransactionSplit)
                .where(TransactionSplit.transaction_id.in_(txn_ids))
                .values(split_type=new_split_type)
            )
    if body.is_active is not None:
        account.is_active = body.is_active

    await db.commit()
    return {
        "id": str(account.id),
        "account_type": account.account_type,
        "is_active": account.is_active,
    }


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
