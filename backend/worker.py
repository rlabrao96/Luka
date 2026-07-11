import redis.asyncio as aioredis
from arq import cron
from arq.connections import RedisSettings
from arq.worker import func as arq_func
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
    refresh_subscriptions_for_user,
    process_merchant_review,
    run_plaid_sync_job,
    schedule_plaid_syncs,
    run_reconciliation_job,
)
from jobs.reconciliation_tick import run_reconciliation_tick_for_household
from modules.email.template_agent import run_template_agent


async def startup(ctx: dict) -> None:
    ctx["redis"] = await aioredis.from_url(settings.redis_url)


async def shutdown(ctx: dict) -> None:
    await ctx["redis"].aclose()


class FastWorkerSettings:
    """Handles webhooks, emails, schedulers, and lightweight cron jobs."""

    functions = [
        # A Gmail history push can carry several template-missing emails, each
        # taking 10-15s of Gemini waterfall — the worker-default 60s timeout
        # killed such batches mid-run. 300s covers the worst realistic batch.
        arq_func(process_email, timeout=300),
        send_invite_email,
        refresh_subscriptions_for_user,
    ]
    cron_jobs = [
        cron(renew_mail_watches, hour=3, minute=0),  # 3am daily
        cron(purge_raw_emails, minute=0),  # every hour
        cron(purge_email_logs, hour=2, minute=0),  # 2am daily
        cron(cleanup_processed_webhooks, hour=4, minute=0),  # 4am daily
        cron(schedule_connect_syncs, hour={0, 6, 12, 18}, minute=0),  # every 6h
        cron(refresh_subscriptions_cache, day={1, 11, 21}, hour=5, minute=30),  # ~every 10 days
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
        run_template_agent,
        run_reconciliation_tick_for_household,
    ]
    cron_jobs = [
        # Daily safety-net pass: catches anything event-driven ticks missed
        # (e.g. emails that arrived while the worker was down).
        cron(run_reconciliation_job, hour=6, minute=0),  # 6am daily
        cron(run_template_agent, hour=2, minute=0),  # 2am daily — template generation
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 5
    job_timeout = 600
    queue_name = "arq:queue:slow"
