import redis.asyncio as aioredis
from arq import cron
from arq.connections import RedisSettings
from core.config import settings
from jobs.tasks import (
    process_email,
    import_fintoc_history,
    renew_mail_watches,
    purge_raw_emails,
    cleanup_processed_webhooks,
    run_fintoc_sync,
)


async def startup(ctx: dict) -> None:
    ctx["redis"] = await aioredis.from_url(settings.redis_url)


async def shutdown(ctx: dict) -> None:
    await ctx["redis"].aclose()


class WorkerSettings:
    functions = [process_email, import_fintoc_history]
    cron_jobs = [
        cron(renew_mail_watches, hour=3, minute=0),  # 3am daily
        cron(purge_raw_emails, minute=0),  # every hour
        cron(cleanup_processed_webhooks, hour=4, minute=0),  # 4am daily
        cron(run_fintoc_sync, hour=2, minute=0),  # 2am nightly
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 60
