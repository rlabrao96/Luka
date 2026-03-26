from arq import create_pool
from arq.connections import RedisSettings
from core.config import settings


async def enqueue_job(function_name: str, **kwargs) -> None:
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await redis.enqueue_job(function_name, **kwargs)
    await redis.aclose()
