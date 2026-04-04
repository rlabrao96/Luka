from arq import create_pool
from arq.connections import RedisSettings
from core.config import settings


async def enqueue_job(function_name: str, *args, **kwargs) -> None:
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await redis.enqueue_job(function_name, *args, **kwargs)
    await redis.aclose()
