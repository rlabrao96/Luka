"""ARQ wrapper for the reconciliation tick orchestrator.

``run_reconciliation_tick_for_household`` is the single unit of work:
enqueued event-driven from email ingest and Plaid sync completion, and
fanned out per household by the daily 6am safety net
(``run_reconciliation_job``). The old all-households-in-one-job wrapper was
removed — it was registered on no worker (the 6am cron silently ran only
transfer detection) and would exceed the slow worker's 600s budget at scale.
"""

import logging
import uuid

from core.database import AsyncSessionLocal
from modules.reconciliation.tick import reconciliation_tick_for_household

logger = logging.getLogger(__name__)


async def run_reconciliation_tick_for_household(ctx: dict, household_id: str) -> dict[str, int]:
    """ARQ task: runs the reconciliation tick for a single household.

    Enqueued at the end of every successful email ingest and Plaid sync so
    pending rows get reconciled within seconds instead of within 15 minutes.
    """
    async with AsyncSessionLocal() as db:
        totals = await reconciliation_tick_for_household(db, uuid.UUID(household_id))
        await db.commit()
    if any(totals.values()):
        logger.info("[RECONCILIATION_TICK] hh=%s %s", household_id, totals)
    return totals
