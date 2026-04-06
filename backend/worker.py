import redis.asyncio as aioredis
from arq import cron
from arq.connections import RedisSettings
from core.config import settings
from jobs.tasks import (
    process_email,
    renew_mail_watches,
    purge_raw_emails,
    purge_email_logs,
    cleanup_processed_webhooks,
    send_invite_email,
    schedule_connect_syncs,
    run_connect_sync,
    refresh_subscriptions_cache,
    process_merchant_review,
    run_plaid_sync_job,
    schedule_plaid_syncs,
    run_reconciliation_job,
)


async def startup(ctx: dict) -> None:
    ctx["redis"] = await aioredis.from_url(settings.redis_url)


async def shutdown(ctx: dict) -> None:
    await ctx["redis"].aclose()


class FastWorkerSettings:
    """Handles webhooks, emails, schedulers, and lightweight cron jobs."""

    functions = [
        process_email,
        send_invite_email,
    ]
    cron_jobs = [
        cron(renew_mail_watches, hour=3, minute=0),  # 3am daily
        cron(purge_raw_emails, minute=0),  # every hour
        cron(purge_email_logs, hour=2, minute=0),  # 2am daily
        cron(cleanup_processed_webhooks, hour=4, minute=0),  # 4am daily
        cron(schedule_connect_syncs, hour={0, 6, 12, 18}, minute=0),  # every 6h
        cron(refresh_subscriptions_cache, hour=5, minute=30),  # 5:30am daily
        cron(schedule_plaid_syncs, hour=3, minute=30),  # 3:30am daily
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 20
    job_timeout = 60
    queue_name = "arq:queue"


class SlowWorkerSettings:
    """Handles bank syncs, LLM processing, and heavy batch jobs."""

    functions = [
        run_connect_sync,
        run_plaid_sync_job,
        process_merchant_review,
    ]
    cron_jobs = [
        cron(run_reconciliation_job, hour=6, minute=0),  # 6am daily
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 5
    job_timeout = 600
    queue_name = "arq:queue:slow"
