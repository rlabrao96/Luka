import redis.asyncio as aioredis
from arq import cron
from core.config import settings
from jobs.tasks import (
    process_email,
    renew_mail_watches,
    purge_raw_emails,
    cleanup_processed_webhooks,
)


async def startup(ctx: dict) -> None:
    ctx["redis"] = await aioredis.from_url(settings.redis_url)


async def shutdown(ctx: dict) -> None:
    await ctx["redis"].aclose()


class WorkerSettings:
    functions = [process_email]
    cron_jobs = [
        cron(renew_mail_watches, hour=3, minute=0),  # 3am daily
        cron(purge_raw_emails, minute=0),  # every hour
        cron(cleanup_processed_webhooks, hour=4, minute=0),  # 4am daily
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = settings.redis_url
    max_jobs = 10
    job_timeout = 60
