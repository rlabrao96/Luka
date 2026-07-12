import logging
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
from modules.currencies.units import to_minor_units
from modules.bank_connect.models import BankCredential
from modules.bank_connect.service import (
    store_credentials,
    delete_credentials,
    get_connection_status,
    get_user_connections,
    trigger_sync,
    verify_callback_token,
    _random_next_sync,
)
from modules.households.models import BankAccount, HouseholdMember
from modules.transactions.models import Transaction, TransactionSplit

logger = logging.getLogger(__name__)

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
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Receive callback from Luka Connect after a scrape completes.

    Authenticated via the per-job HMAC token we embedded in the callback URL
    when triggering the scrape — this endpoint creates real transactions and
    deletes matched email rows, so it must not be open to the internet.
    """
    # Strict when a token is PRESENT but wrong; grace path when absent.
    # INCIDENT 2026-07-12: requiring the token unconditionally 401'd the
    # scraper's queued callbacks (their URLs predate the token change — and
    # the scraper may use a fixed configured webhook URL), causing an
    # infinite retry storm and dropped bank syncs. Without a token the
    # unguessable per-job UUID remains the auth factor (pre-H1 posture) and
    # unknown job ids still 404 below. Flip to strict once Luka Connect
    # confirms it echoes tokenized callback URLs (see NEXT-STEPS).
    if token is not None and not verify_callback_token(body.jobId, token):
        raise HTTPException(status_code=401, detail="Invalid callback token")
    if token is None:
        logger.warning(
            "connect callback WITHOUT token for job %s — grace path (legacy URL)",
            body.jobId,
        )
    try:
        job_uuid = uuid.UUID(body.jobId)
    except ValueError:
        raise HTTPException(status_code=400, detail="Malformed job ID")
    result = await db.execute(
        select(BankCredential).where(BankCredential.current_job_id == job_uuid)
    )
    cred = result.scalar_one_or_none()
    if not cred:
        # ACK stale/unknown jobs with 200 — the scraper treats non-2xx as
        # retryable and will hammer a dead job forever (INCIDENT 2026-07-12:
        # 7 stale callbacks retried every 10s for hours). A job id that no
        # longer matches means we already resolved that sync; there is
        # nothing to redo and nothing sensitive in acknowledging it.
        logger.warning("connect callback for unknown/stale job %s — acked and ignored", body.jobId)
        return {"status": "ignored_unknown_job"}

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

        # Event-driven reconciliation tick: mirrors the Plaid + email-ingest
        # paths so LATAM users (Luka Connect) get the same automatic
        # post-sync reconciliation. Runs on the slow worker because a tick
        # can exceed 60s. Failures here must NOT fail the sync — best effort.
        hh_result = await db.execute(
            select(HouseholdMember.household_id).where(HouseholdMember.user_id == cred.user_id)
        )
        hh_id = hh_result.scalar_one_or_none()
        if hh_id is not None:
            await _enqueue_reconciliation_tick(hh_id)

        return {"status": "ok", "created": created, "enriched": enriched, "skipped": skipped}

    return {"status": "ack"}


async def _enqueue_reconciliation_tick(household_id: uuid.UUID) -> None:
    """Enqueue a per-household reconciliation tick on the slow worker.

    Best-effort: never raises into the caller. The reconciliation_tick cron
    still runs every 15 minutes as a safety net, so a missed enqueue here is
    not data-loss — just slightly delayed reconciliation.
    """
    import logging

    from arq import create_pool
    from arq.connections import RedisSettings

    logger = logging.getLogger(__name__)

    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        try:
            await redis.enqueue_job(
                "run_reconciliation_tick_for_household",
                str(household_id),
                _queue_name="arq:queue:slow",
            )
        finally:
            await redis.aclose()
    except Exception as exc:  # noqa: BLE001 — best-effort enqueue
        logger.warning(
            "Failed to enqueue run_reconciliation_tick_for_household for household %s: %s",
            household_id,
            exc,
        )


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

    # Pre-fetch account types so joint accounts default their splits to "shared".
    # Mirrors the email + Plaid ingestion paths.
    acct_type_result = await db.execute(
        select(BankAccount.id, BankAccount.account_type).where(
            BankAccount.household_id == household_id
        )
    )
    account_type_map: dict[uuid.UUID, str] = {
        acct_id: acct_type for acct_id, acct_type in acct_type_result.all()
    }

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

        from sqlalchemy import update as sql_update

        # Resolve bank account for the movement
        acct_name = mov.get("accountName", "")
        currency = mov.get("currency", "CLP")
        source = mov.get("source", "")
        if source in ("credit_card_billed", "credit_card_unbilled"):
            ba_id = _resolve_cc_account(mov, ba_map)
        else:
            ba_id = ba_map.get((acct_name, currency))

        # Stored amounts are integer minor units — compare in the same scale
        # the mapper writes, or dedup/matching breaks for 2-decimal currencies.
        scaled_amount = to_minor_units(mov["amount"], currency)

        # Dedup: check for an existing connect transaction with same bank_account,
        # same amount, and same exact timestamp. This catches both:
        # (a) re-runs of the same scrape (identical rows)
        # (b) previously-promoted email transactions whose name may now differ
        #     from the scraper's bank description (e.g. "Camila Chahuan" vs
        #     "Traspaso A:Camila Chahuan")
        dedup_conditions = [
            Transaction.user_id == cred.user_id,
            Transaction.source == "connect",
            Transaction.amount == scaled_amount,
            Transaction.currency == currency,
            Transaction.transaction_date == mov_date,
        ]
        if ba_id:
            dedup_conditions.append(Transaction.bank_account_id == ba_id)
        existing = await db.execute(select(Transaction.id).where(*dedup_conditions).limit(1))
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        # Check for email match (signed amount + currency exact, date ±1 day).
        # Signed equality matters: an income email must never consolidate into
        # an expense movement; currency matters because a USD 50.00 email
        # (stored 5000) structurally collides with a CLP $5.000 movement.
        email_match = await db.execute(
            select(Transaction)
            .where(
                Transaction.user_id == cred.user_id,
                Transaction.source_type == "email",
                Transaction.amount == scaled_amount,
                Transaction.currency == currency,
                Transaction.transaction_date >= mov_date - timedelta(days=1),
                Transaction.transaction_date <= mov_date + timedelta(days=1),
            )
            .limit(1)
        )
        email_txn = email_match.scalar_one_or_none()

        # Create the new Connect transaction
        txn_data = map_movement_to_transaction(
            movement=mov,
            user_id=str(cred.user_id),
            household_id=str(household_id),
            bank_account_id=str(ba_id) if ba_id else None,
        )
        txn = Transaction(**txn_data)
        db.add(txn)
        await db.flush()

        is_transfer = txn.transaction_type == "transfer"

        if email_txn:
            # Transfer enrichment from the email to the new Connect transaction.
            # For transfers (CC payments, own-account moves), don't copy category
            # or splits — transfers are displayed as "Ajuste entre cuentas".
            if not is_transfer:
                if email_txn.category and not txn.category:
                    txn.category = email_txn.category
                if email_txn.merchant_id and not txn.merchant_id:
                    txn.merchant_id = email_txn.merchant_id
                # Re-link the email's splits to the new Connect transaction
                await db.execute(
                    sql_update(TransactionSplit)
                    .where(TransactionSplit.transaction_id == email_txn.id)
                    .values(transaction_id=txn.id)
                )
            else:
                # Transfer: drop the email's splits (if any) since transfers have none
                await db.execute(
                    delete(TransactionSplit).where(TransactionSplit.transaction_id == email_txn.id)
                )
            # Preserve the cleaner merchant name from the email (e.g. "Camila Chahuan"
            # instead of "Traspaso A:Camila Chahuan")
            if email_txn.raw_merchant_name:
                txn.raw_merchant_name = email_txn.raw_merchant_name
            # Delete the email transaction
            await db.execute(delete(Transaction).where(Transaction.id == email_txn.id))
            enriched += 1
        else:
            # No email match. ensure_default_split is a no-op for transfers and
            # idempotent otherwise — single source of truth for the personal default.
            from modules.transactions.service import ensure_default_split

            is_joint = ba_id is not None and account_type_map.get(ba_id) == "joint"
            await ensure_default_split(
                db, txn, default_split_type="shared" if is_joint else "personal"
            )
        created += 1

    return created, enriched, skipped
