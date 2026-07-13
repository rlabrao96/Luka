import uuid
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.households.models import BankAccount
from modules.households.auth import require_membership
from modules.transactions.attribution import account_person_balances
from modules.transactions.models import Transaction, TransactionSplit

router = APIRouter(prefix="/bank-accounts", tags=["bank-accounts"])


@router.get("")
async def list_bank_accounts(
    household_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List bank accounts visible to the current user in this household.

    Returns:
      - Accounts owned by the current user (user_id == current_user.id)
      - Joint household accounts (account_type == 'joint'), regardless of owner

    A partner's personal/partner accounts are NEVER returned. This endpoint
    backs the home BalanceCard and the settings BankAccountsSection — neither
    should ever expose a partner's raw balance.
    """
    await require_membership(household_id, current_user.id, db)

    result = await db.execute(
        select(BankAccount).where(
            BankAccount.household_id == household_id,
            or_(
                BankAccount.user_id == current_user.id,
                BankAccount.account_type == "joint",
            ),
        )
    )
    accounts = result.scalars().all()

    return [
        {
            "id": str(a.id),
            "bank_name": a.bank_name,
            "account_type": a.account_type,
            "account_kind": a.account_kind,
            "account_name": a.account_name,
            "account_number": a.account_number,
            "cardholder_name": a.cardholder_name,
            # Groups cards that share one Plaid login, so the UI can hint when
            # multiple credit cards on the same connection may include a
            # partner's authorized-user card. Internal id, not PII.
            "plaid_item_id": str(a.plaid_item_id) if a.plaid_item_id else None,
            "currency": a.currency,
            "is_active": a.is_active,
            "user_id": str(a.user_id),
            "balance_current": a.balance_current,
            "balance_limit": a.balance_limit,
            "last_synced_at": a.last_synced_at.isoformat() if a.last_synced_at else None,
            "country": a.country,
            "provider": a.provider,
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
    )
    db.add(bank_account)
    await db.commit()
    await db.refresh(bank_account)
    # Trigger subscription recomputation 30 min after bank link
    from jobs.queue import enqueue_job

    await enqueue_job("refresh_subscriptions_for_user", str(current_user.id), _defer_by=1800)
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

    if body.account_type is not None and body.account_type != account.account_type:
        account.account_type = body.account_type
        # Backfill existing splits to match the new account type
        new_split_type = "shared" if body.account_type == "joint" else body.account_type
        txn_ids_result = await db.execute(
            select(Transaction.id).where(Transaction.bank_account_id == account_id)
        )
        txn_ids = [row[0] for row in txn_ids_result.fetchall()]
        if txn_ids:
            # Update existing splits
            await db.execute(
                update(TransactionSplit)
                .where(TransactionSplit.transaction_id.in_(txn_ids))
                .values(split_type=new_split_type)
            )
            # Create splits for transactions that don't have one yet
            existing_result = await db.execute(
                select(TransactionSplit.transaction_id).where(
                    TransactionSplit.transaction_id.in_(txn_ids)
                )
            )
            existing_ids = {row[0] for row in existing_result.fetchall()}
            missing_ids = [tid for tid in txn_ids if tid not in existing_ids]
            if missing_ids:
                await db.execute(
                    insert(TransactionSplit),
                    [{"transaction_id": tid, "split_type": new_split_type} for tid in missing_ids],
                )
    if body.is_active is not None:
        account.is_active = body.is_active

    await db.commit()
    return {
        "id": str(account.id),
        "account_type": account.account_type,
        "is_active": account.is_active,
    }


@router.get("/{account_id}/person-balances")
async def get_account_person_balances(
    account_id: uuid.UUID,
    household_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Per-person gastos/pagos/saldo breakdown for a shared card.

    Owner-only: the breakdown exposes the owner's OWN charges/payments on the
    card, so a partner must never see it. A non-owner household member gets 403.
    """
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
        raise HTTPException(status_code=403, detail="Only the account owner can see the breakdown")

    return {
        "balances": await account_person_balances(db, account_id),
        "currency": account.currency,
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
