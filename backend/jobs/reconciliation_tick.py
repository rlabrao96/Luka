"""ARQ wrapper for the reconciliation tick orchestrator.

Registered as a cron job on the slow worker (every 15 minutes). Opens an
async session and delegates to `reconciliation_tick_all_households`, which
iterates every household and commits between them so a single failure does
not roll back prior progress.
"""

from arq import cron

from core.database import AsyncSessionLocal
from modules.reconciliation.tick import reconciliation_tick_all_households


async def run_reconciliation_tick(ctx: dict) -> dict[str, int]:
    """ARQ task: runs a full reconciliation tick across every household."""
    async with AsyncSessionLocal() as db:
        totals = await reconciliation_tick_all_households(db)
    if any(totals.values()):
        print(f"[RECONCILIATION_TICK] {totals}", flush=True)
    return totals


reconciliation_tick_cron = cron(
    run_reconciliation_tick,
    minute={0, 15, 30, 45},
    run_at_startup=False,
)
