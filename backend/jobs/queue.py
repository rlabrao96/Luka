from arq import create_pool
from arq.connections import RedisSettings
from core.config import settings


async def enqueue_job(function_name: str, **kwargs) -> None:
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await redis.enqueue_job(function_name, **kwargs)
    await redis.aclose()


async def enqueue_fintoc_history_import(bank_account_id: str) -> None:
    """Enqueue a 90-day Fintoc history import for a single bank account."""
    await enqueue_job("import_fintoc_history", bank_account_id=bank_account_id)
