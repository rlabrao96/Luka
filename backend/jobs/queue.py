import asyncio

from arq import create_pool
from arq.connections import RedisSettings
from core.config import settings

SLOW_JOBS = {
    "run_connect_sync",
    "run_plaid_sync_job",
    "process_merchant_review",
    "run_reconciliation_job",
    "run_reconciliation_tick_for_household",
}

# Lazy module-level pool: enqueue_job is called in loops (cron schedulers) and
# on the live email hot path — a fresh TCP+auth handshake per call is waste.
_pool = None
_pool_lock = asyncio.Lock()


async def _get_pool():
    global _pool
    if _pool is None:
        async with _pool_lock:
            if _pool is None:
                _pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    return _pool


async def enqueue_job(function_name: str, *args, **kwargs) -> None:
    queue_name = "arq:queue:slow" if function_name in SLOW_JOBS else "arq:queue"
    redis = await _get_pool()
    await redis.enqueue_job(function_name, *args, _queue_name=queue_name, **kwargs)
