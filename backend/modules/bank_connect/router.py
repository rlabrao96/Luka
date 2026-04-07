import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from core.security import get_current_user
from jobs.queue import enqueue_job
from modules.bank_connect.accounts import ensure_accounts
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
from modules.transactions.models import Transaction, TransactionSplit

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
    allBalances: dict | None = None  # Was "balances" — matches scraper field name
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
    await trigger_sync(db=db, cred=cred, days_back=90, callback_url=callback_url)
    return {"status": "started", "bank_code": body.bank_code, "job_id": str(cred.current_job_id)}


@router.delete("/disconnect")
async def disconnect_bank(
    bank_code: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hard delete credentials, auto-created accounts, and their transactions."""
    from modules.bank_connect.accounts import BANK_NAMES

    bank_name = BANK_NAMES.get(bank_code, bank_code)

    # Find auto-created accounts for this bank (have account_name set)
    acct_result = await db.execute(
        select(BankAccount.id).where(
            BankAccount.user_id == user.id,
            BankAccount.bank_name == bank_name,
            BankAccount.account_name.isnot(None),
        )
    )
    acct_ids = [row[0] for row in acct_result.fetchall()]

    if acct_ids:
        # Delete splits → transactions → accounts (respect FK order)
        from modules.transactions.models import TransactionSplit

        txn_result = await db.execute(
            select(Transaction.id).where(Transaction.bank_account_id.in_(acct_ids))
        )
        txn_ids = [row[0] for row in txn_result.fetchall()]
        if txn_ids:
            await db.execute(
                delete(TransactionSplit).where(TransactionSplit.transaction_id.in_(txn_ids))
            )
            await db.execute(delete(Transaction).where(Transaction.id.in_(txn_ids)))
        await db.execute(delete(BankAccount).where(BankAccount.id.in_(acct_ids)))

    # Also delete any connect transactions not linked to an account
    await db.execute(
        delete(Transaction).where(
            Transaction.user_id == user.id,
            Transaction.source_type == "connect",
            Transaction.bank_account_id.is_(None),
        )
    )

    await delete_credentials(db=db, user_id=str(user.id), bank_code=bank_code)
    return {"status": "disconnected"}


@router.post("/sync")
async def manual_sync(
    bank_code: str,
    days_back: int = 4,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a manual sync (async with webhook callback)."""
    cred = await get_connection_status(db=db, user_id=str(user.id), bank_code=bank_code)
    if not cred:
        raise HTTPException(status_code=404, detail="No connection found for this bank")
    callback_url = f"{settings.backend_public_url}/bank-connect/webhooks/luka-connect"
    result = await trigger_sync(db=db, cred=cred, days_back=days_back, callback_url=callback_url)
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

    if body.status == "completed":
        # Always run account creation/balance updates, even with no movements
        ba_map = await ensure_accounts(
            db=db,
            user_id=cred.user_id,
            bank_code=cred.bank_code,
            movements=body.movements,
            all_balances=body.allBalances,
            credit_cards=body.creditCards,
        )

        created, enriched, skipped = 0, 0, 0
        if body.movements:
            created, enriched, skipped = await _process_movements(
                db=db, cred=cred, movements=body.movements, ba_map=ba_map
            )

        cred.last_sync_at = datetime.now(timezone.utc)
        cred.last_sync_status = "success"
        cred.current_job_id = None
        cred.next_sync_at = _random_next_sync()
        await db.commit()

        # Trigger merchant review pipeline if new transactions were created
        if created > 0:
            from modules.merchant_review.models import MerchantReviewJob

            review_job = MerchantReviewJob(
                user_id=cred.user_id,
                bank_credential_id=cred.id,
            )
            db.add(review_job)
            await db.commit()

            await enqueue_job("process_merchant_review", str(review_job.id))

        # Bust subscriptions cache so next visit recomputes with new data
        from modules.subscriptions.service import invalidate_subscriptions_cache

        await invalidate_subscriptions_cache(cred.user_id)

        return {"status": "ok", "created": created, "enriched": enriched, "skipped": skipped}

    return {"status": "ack"}


def _resolve_account(mov: dict, ba_map: dict[tuple[str, str], uuid.UUID]) -> uuid.UUID | None:
    """Resolve bank_account_id for any movement."""
    source = mov.get("source", "")
    if source in ("credit_card_billed", "credit_card_unbilled"):
        return _resolve_cc_account(mov, ba_map)
    return ba_map.get((mov.get("accountName", ""), mov.get("currency", "CLP")))


def _resolve_cc_account(mov: dict, ba_map: dict[tuple[str, str], uuid.UUID]) -> uuid.UUID | None:
    """Resolve CC movement to card account using cardLabel (precise) or fallback (first match)."""
    currency = mov.get("currency", "CLP")
    card_label = mov.get("cardLabel")

    if card_label:
        # Precise match: "Visa Signature ****5032" + "Nacional"/"Internacional"
        suffix = "Internacional" if currency == "USD" else "Nacional"
        ba_id = ba_map.get((f"{card_label} {suffix}", currency))
        if ba_id:
            return ba_id

    # Fallback: first CC account for this currency
    for (name, curr), acct_id in ba_map.items():
        if curr == currency and ("Nacional" in name or "Internacional" in name):
            return acct_id
    return None


async def _process_movements(
    db: AsyncSession,
    cred: BankCredential,
    movements: list[dict],
    ba_map: dict[tuple[str, str], uuid.UUID],
) -> tuple[int, int, int]:
    """Process movements: dedup, reconcile with email txns, create new ones."""
    created = 0
    enriched = 0
    skipped = 0

    # Pre-fetch household_id once (not per movement)
    hm_result = await db.execute(
        select(HouseholdMember.household_id).where(HouseholdMember.user_id == cred.user_id)
    )
    household_id = hm_result.scalar_one_or_none()
    if not household_id:
        return 0, 0, len(movements)

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

        # Check for email match (abs amount exact + date ±1 day)
        from sqlalchemy import func as sa_func

        email_match = await db.execute(
            select(Transaction)
            .where(
                Transaction.user_id == cred.user_id,
                Transaction.source_type == "email",
                sa_func.abs(Transaction.amount) == abs(mov["amount"]),
                Transaction.transaction_date >= mov_date - timedelta(days=1),
                Transaction.transaction_date <= mov_date + timedelta(days=1),
            )
            .limit(1)
        )
        email_txn = email_match.scalar_one_or_none()

        if email_txn:
            email_txn.transaction_date = mov_date
            # Also link to bank account
            ba_id_for_email = _resolve_account(mov, ba_map)
            email_txn.bank_account_id = ba_id_for_email
            enriched += 1
        else:
            acct_name = mov.get("accountName", "")
            currency = mov.get("currency", "CLP")
            source = mov.get("source", "")

            if source in ("credit_card_billed", "credit_card_unbilled"):
                ba_id = _resolve_cc_account(mov, ba_map)
            else:
                ba_id = ba_map.get((acct_name, currency))

            txn_data = map_movement_to_transaction(
                movement=mov,
                user_id=str(cred.user_id),
                household_id=str(household_id),
                bank_account_id=str(ba_id) if ba_id else None,
            )
            txn = Transaction(**txn_data)
            db.add(txn)
            await db.flush()
            db.add(TransactionSplit(transaction_id=txn.id, split_type="personal"))
            created += 1

    return created, enriched, skipped
