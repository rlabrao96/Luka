import redis.asyncio as aioredis
from arq import cron
from arq.connections import RedisSettings
from core.config import settings
from jobs.tasks import (
    process_email,
    renew_mail_watches,
    purge_raw_emails,
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


class WorkerSettings:
    functions = [
        process_email,
        send_invite_email,
        run_connect_sync,
        run_plaid_sync_job,
        process_merchant_review,
    ]
    cron_jobs = [
        cron(renew_mail_watches, hour=3, minute=0),  # 3am daily
        cron(purge_raw_emails, minute=0),  # every hour
        cron(cleanup_processed_webhooks, hour=4, minute=0),  # 4am daily
        cron(schedule_connect_syncs, minute=0),  # Every hour, check for due syncs
        cron(refresh_subscriptions_cache, hour=5, minute=30),  # 5:30am daily
        cron(schedule_plaid_syncs, hour=3, minute=30),  # Daily 3:30am UTC — sync all Plaid items
        cron(run_reconciliation_job, hour=6, minute=0),  # Daily 6am UTC — transfer detection
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 300  # 5 min — enough for bank scrape + 2FA wait
