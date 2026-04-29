"""ARQ wrappers for the reconciliation tick orchestrator.

Two task variants exist:

- ``run_reconciliation_tick``: runs a full pass across every household.
  Kept available for the daily safety-net cron at 6am (``run_reconciliation_job``)
  and ad-hoc invocations.
- ``run_reconciliation_tick_for_household``: per-household variant enqueued
  event-driven from email ingest and Plaid sync completion. This replaces
  the old every-15-minute cron that ticked all households unconditionally.
"""

import uuid

from core.database import AsyncSessionLocal
from modules.reconciliation.tick import (
    reconciliation_tick_all_households,
    reconciliation_tick_for_household,
)


async def run_reconciliation_tick(ctx: dict) -> dict[str, int]:
    """ARQ task: runs a full reconciliation tick across every household."""
    async with AsyncSessionLocal() as db:
        totals = await reconciliation_tick_all_households(db)
    if any(totals.values()):
        print(f"[RECONCILIATION_TICK] {totals}", flush=True)
    return totals


async def run_reconciliation_tick_for_household(ctx: dict, household_id: str) -> dict[str, int]:
    """ARQ task: runs the reconciliation tick for a single household.

    Enqueued at the end of every successful email ingest and Plaid sync so
    pending rows get reconciled within seconds instead of within 15 minutes.
    """
    async with AsyncSessionLocal() as db:
        totals = await reconciliation_tick_for_household(db, uuid.UUID(household_id))
        await db.commit()
    if any(totals.values()):
        print(f"[RECONCILIATION_TICK] hh={household_id} {totals}", flush=True)
    return totals
