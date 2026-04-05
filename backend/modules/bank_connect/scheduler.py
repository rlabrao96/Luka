from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from modules.bank_connect.models import BankCredential

_STUCK_JOB_TIMEOUT = timedelta(hours=2)


async def get_due_syncs(db: AsyncSession) -> list[BankCredential]:
    """Find all credentials due for sync (next_sync_at <= now)."""
    now = datetime.now(timezone.utc)

    # Unstick jobs that never received a callback (e.g. Connect crashed)
    await _clear_stuck_jobs(db, now)

    result = await db.execute(
        select(BankCredential).where(
            BankCredential.next_sync_at <= now,
            BankCredential.next_sync_at.isnot(None),
            BankCredential.current_job_id.is_(None),  # Not already syncing
            BankCredential.last_sync_status != "failed_login",  # Not disabled
        )
    )
    return list(result.scalars().all())


async def _clear_stuck_jobs(db: AsyncSession, now: datetime) -> None:
    """Reset credentials stuck in 'in_progress' for over 2 hours."""
    cutoff = now - _STUCK_JOB_TIMEOUT
    result = await db.execute(
        select(BankCredential).where(
            BankCredential.current_job_id.isnot(None),
            BankCredential.updated_at < cutoff,
        )
    )
    stuck = result.scalars().all()
    for cred in stuck:
        cred.current_job_id = None
        cred.last_sync_status = "failed_timeout"
    if stuck:
        await db.commit()
