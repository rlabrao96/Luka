from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from modules.bank_connect.models import BankCredential


async def get_due_syncs(db: AsyncSession) -> list[BankCredential]:
    """Find all credentials due for sync (next_sync_at <= now)."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(BankCredential).where(
            BankCredential.next_sync_at <= now,
            BankCredential.next_sync_at.isnot(None),
            BankCredential.current_job_id.is_(None),  # Not already syncing
            BankCredential.last_sync_status != "failed_login",  # Not disabled
        )
    )
    return list(result.scalars().all())
