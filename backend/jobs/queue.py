from arq import create_pool
from arq.connections import RedisSettings
from core.config import settings

SLOW_JOBS = {
    "run_connect_sync",
    "run_plaid_sync_job",
    "process_merchant_review",
    "run_reconciliation_job",
}


async def enqueue_job(function_name: str, *args, **kwargs) -> None:
    queue_name = "arq:queue:slow" if function_name in SLOW_JOBS else "arq:queue"
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        await redis.enqueue_job(function_name, *args, _queue_name=queue_name, **kwargs)
    finally:
        await redis.aclose()
