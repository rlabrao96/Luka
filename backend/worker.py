import redis.asyncio as aioredis
from arq.connections import RedisSettings
from core.config import settings


async def startup(ctx: dict) -> None:
    ctx["redis"] = await aioredis.from_url(settings.redis_url)


async def shutdown(ctx: dict) -> None:
    await ctx["redis"].aclose()


class WorkerSettings:
    functions = []  # jobs registered in later plans
    cron_jobs = []
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
