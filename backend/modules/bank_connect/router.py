import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from core.security import get_current_user
from modules.bank_connect.mapper import (
    map_movement_to_transaction,
    parse_movement_date,
)
from modules.bank_connect.models import BankCredential
from modules.bank_connect.service import (
    store_credentials,
    delete_credentials,
    get_connection_status,
    get_user_connections,
    trigger_sync,
    _random_next_sync,
)
from modules.households.models import BankAccount, HouseholdMember
from modules.transactions.models import Transaction

router = APIRouter(prefix="/bank-connect", tags=["bank-connect"])


class ConnectRequest(BaseModel):
    bank_code: str
    rut: str
    password: str


class SyncStatusResponse(BaseModel):
    bank_code: str
    last_sync_at: str | None
    last_sync_status: str | None
    current_job_id: str | None
    next_sync_at: str | None


class ConnectCallback(BaseModel):
    jobId: str
    status: str
    movements: list[dict] | None = None
    balances: dict | None = None
    creditCards: list[dict] | None = None
    error: str | None = None


@router.post("/connect")
async def connect_bank(
    body: ConnectRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Store encrypted credentials and trigger initial full sync (async).
    Frontend polls GET /bank-connect/sync-status to track progress."""
    cred = await store_credentials(
        db=db,
        user_id=str(user.id),
        bank_code=body.bank_code,
        rut=body.rut,
        password=body.password,
    )
    callback_url = f"{settings.backend_public_url}/bank-connect/webhooks/luka-connect"
    await trigger_sync(db=db, cred=cred, mode="full", callback_url=callback_url)
    return {"status": "started", "bank_code": body.bank_code, "job_id": str(cred.current_job_id)}


@router.delete("/disconnect")
async def disconnect_bank(
    bank_code: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hard delete credentials and stop scheduling."""
    await delete_credentials(db=db, user_id=str(user.id), bank_code=bank_code)
    return {"status": "disconnected"}


@router.post("/sync")
async def manual_sync(
    bank_code: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a manual sync (async with webhook callback)."""
    cred = await get_connection_status(db=db, user_id=str(user.id), bank_code=bank_code)
    if not cred:
        raise HTTPException(status_code=404, detail="No connection found for this bank")
    callback_url = f"{settings.backend_public_url}/bank-connect/webhooks/luka-connect"
    result = await trigger_sync(db=db, cred=cred, mode="recent", callback_url=callback_url)
    return result


@router.get("/sync-status")
async def sync_status(
    bank_code: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Poll sync progress (for frontend during initial connection)."""
    cred = await get_connection_status(db=db, user_id=str(user.id), bank_code=bank_code)
    if not cred:
        raise HTTPException(status_code=404, detail="No connection found")
    return SyncStatusResponse(
        bank_code=cred.bank_code,
        last_sync_at=cred.last_sync_at.isoformat() if cred.last_sync_at else None,
        last_sync_status=cred.last_sync_status,
        current_job_id=str(cred.current_job_id) if cred.current_job_id else None,
        next_sync_at=cred.next_sync_at.isoformat() if cred.next_sync_at else None,
    )


@router.get("/connections")
async def list_connections(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all connected banks for the current user."""
    connections = await get_user_connections(db=db, user_id=str(user.id))
    return [
        {
            "bank_code": c.bank_code,
            "last_sync_at": c.last_sync_at.isoformat() if c.last_sync_at else None,
            "last_sync_status": c.last_sync_status,
            "next_sync_at": c.next_sync_at.isoformat() if c.next_sync_at else None,
        }
        for c in connections
    ]


@router.post("/webhooks/luka-connect")
async def handle_connect_callback(
    body: ConnectCallback,
    db: AsyncSession = Depends(get_db),
):
    """Receive callback from Luka Connect after a scrape completes."""
    result = await db.execute(
        select(BankCredential).where(BankCredential.current_job_id == uuid.UUID(body.jobId))
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Unknown job ID")

    if body.status == "awaiting_2fa":
        cred.last_sync_status = "awaiting_2fa"
        await db.commit()
        return {"status": "ack"}

    if body.status == "failed":
        cred.last_sync_status = f"failed_{body.error or 'unknown'}"
        cred.current_job_id = None
        if body.error == "login_failed":
            cred.next_sync_at = None  # Disable auto-sync
        await db.commit()
        return {"status": "ack"}

    if body.status == "completed" and body.movements:
        created, enriched, skipped = await _process_movements(
            db=db, cred=cred, movements=body.movements
        )
        cred.last_sync_at = datetime.now(timezone.utc)
        cred.last_sync_status = "success"
        cred.current_job_id = None
        cred.next_sync_at = _random_next_sync()
        await db.commit()
        return {"status": "ok", "created": created, "enriched": enriched, "skipped": skipped}

    return {"status": "ack"}


async def _process_movements(
    db: AsyncSession, cred: BankCredential, movements: list[dict]
) -> tuple[int, int, int]:
    """Process movements: dedup, reconcile with email txns, create new ones."""
    created = 0
    enriched = 0
    skipped = 0

    # Pre-fetch household_id and bank_accounts once (not per movement)
    hm_result = await db.execute(
        select(HouseholdMember.household_id).where(HouseholdMember.user_id == cred.user_id)
    )
    household_id = hm_result.scalar_one_or_none()
    if not household_id:
        return 0, 0, len(movements)

    ba_result = await db.execute(
        select(BankAccount.id, BankAccount.account_number).where(
            BankAccount.user_id == cred.user_id
        )
    )
    ba_map = {row[1]: row[0] for row in ba_result.fetchall() if row[1]}

    for mov in movements:
        # Skip movements with missing or invalid dates
        if not mov.get("date") or not isinstance(mov["date"], str) or len(mov["date"]) < 8:
            skipped += 1
            continue

        try:
            mov_date = parse_movement_date(mov["date"], mov.get("time"))
        except Exception:
            skipped += 1
            continue

        # Check for exact duplicate (same movement already imported via connect)
        existing = await db.execute(
            select(Transaction.id)
            .where(
                Transaction.user_id == cred.user_id,
                Transaction.source_type == "connect",
                Transaction.raw_merchant_name == mov["description"],
                Transaction.amount == mov["amount"],
                Transaction.transaction_date == mov_date,
            )
            .limit(1)
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        # Check for email match (amount exact + date ±1 day)
        email_match = await db.execute(
            select(Transaction)
            .where(
                Transaction.user_id == cred.user_id,
                Transaction.source_type == "email",
                Transaction.amount == mov["amount"],
                Transaction.transaction_date >= mov_date - timedelta(days=1),
                Transaction.transaction_date <= mov_date + timedelta(days=1),
            )
            .limit(1)
        )
        email_txn = email_match.scalar_one_or_none()

        if email_txn:
            email_txn.transaction_date = mov_date
            enriched += 1
        else:
            ba_id = ba_map.get(mov.get("accountNumber"))

            txn_data = map_movement_to_transaction(
                movement=mov,
                user_id=str(cred.user_id),
                household_id=str(household_id),
                bank_account_id=str(ba_id) if ba_id else None,
            )
            txn = Transaction(**txn_data)
            db.add(txn)
            created += 1

    await db.commit()
    return created, enriched, skipped
