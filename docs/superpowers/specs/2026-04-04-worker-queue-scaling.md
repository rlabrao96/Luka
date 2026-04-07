# Worker Queue Scaling: Fast vs Slow Jobs

## Problem

Luka runs a single ARQ worker with `max_jobs=10`. All jobs — fast webhooks, slow bank syncs, LLM-heavy merchant reviews, and cron schedulers — compete for the same 10 slots. At 200 users:

- **Hourly bank syncs**: `schedule_connect_syncs` + `schedule_plaid_syncs` could enqueue 200+ sync jobs at once
- **Email webhooks**: Gmail/Outlook push notifications need sub-second ACK → if all 10 slots are occupied by 30s merchant reviews, emails queue up
- **LLM bottleneck**: `process_merchant_review` calls `lookup_merchant` (LLM) per merchant × per user → rate limits hit quickly
- **Cascade failure**: A burst of sync jobs fills slots → emails back up → Gmail retries → more pressure

## Current Architecture

```
┌─────────────────────────────────────────────┐
│           Single ARQ Worker                 │
│           max_jobs=10, timeout=300s         │
│                                             │
│  ┌─────────────┐  ┌──────────────────────┐  │
│  │ Fast Jobs    │  │ Slow Jobs            │  │
│  │              │  │                      │  │
│  │ process_email│  │ run_connect_sync     │  │
│  │ send_invite  │  │ run_plaid_sync_job   │  │
│  │              │  │ process_merchant_rev │  │
│  └─────────────┘  └──────────────────────┘  │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │ Cron Schedulers (7 jobs)            │    │
│  │ renew_mail_watches, purge_raw,      │    │
│  │ cleanup_webhooks, schedule_syncs,   │    │
│  │ refresh_subs, schedule_plaid,       │    │
│  │ run_reconciliation                  │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

**The risk**: 10 concurrent `run_connect_sync` jobs (each waiting up to 5min for 2FA) block everything.

## Proposed Architecture: Two Workers, Two Queues

```
┌──────────────────────────────┐    ┌──────────────────────────────┐
│  Fast Worker (luka-worker)   │    │  Slow Worker (luka-worker-bg)│
│  queue: "arq:queue"          │    │  queue: "arq:queue:slow"     │
│  max_jobs: 20                │    │  max_jobs: 5                 │
│  job_timeout: 60s            │    │  job_timeout: 600s           │
│                              │    │                              │
│  process_email          ⚡   │    │  run_connect_sync       🐢  │
│  send_invite_email      ⚡   │    │  run_plaid_sync_job     🐢  │
│  schedule_connect_syncs ⚡   │    │  process_merchant_review🐢  │
│  schedule_plaid_syncs   ⚡   │    │  run_reconciliation     🐢  │
│  purge_raw_emails       ⚡   │    │                              │
│  cleanup_webhooks       ⚡   │    │                              │
│  renew_mail_watches     ⚡   │    │                              │
│  refresh_subs_cache     ⚡   │    │                              │
└──────────────────────────────┘    └──────────────────────────────┘
```

### Job Classification

| Job | Queue | Why |
|-----|-------|-----|
| `process_email` | **fast** | Webhook-triggered, needs <1s response. Pure I/O (fetch email, parse, DB write) |
| `send_invite_email` | **fast** | Single API call to Resend, <2s |
| `schedule_connect_syncs` | **fast** | Lightweight scheduler — queries DB, enqueues N slow jobs, finishes in seconds |
| `schedule_plaid_syncs` | **fast** | Lightweight scheduler — enqueues N Plaid syncs, finishes in seconds |
| `renew_mail_watches` | **fast** | API calls to Google/Microsoft, <10s |
| `purge_raw_emails` | **fast** | Single DB delete, <5s |
| `cleanup_processed_webhooks` | **fast** | Single DB delete, <5s |
| `refresh_subscriptions_cache` | **fast** | DB reads + Redis writes, <30s |
| `run_connect_sync` | **slow** | Bank scrape, may wait for 2FA, up to 5min |
| `run_plaid_sync_job` | **slow** | Plaid API sync + enqueues merchant review |
| `process_merchant_review` | **slow** | LLM calls (grouping + categorization), 10-60s per user |
| `run_reconciliation_job` | **slow** | Cross-household DB scan, could be heavy at scale |

### Key Principle

**Fast queue must never block.** If the fast worker is full, emails get delayed and Gmail/Outlook retry with backoff, potentially dropping notifications. The slow queue can back up — users wait a bit longer for their bank sync, that's fine.

## Implementation

### Step 1: Split WorkerSettings into two classes

```python
# backend/worker.py

class FastWorkerSettings:
    """Handles webhooks, emails, schedulers, and lightweight cron jobs."""
    functions = [
        process_email,
        send_invite_email,
    ]
    cron_jobs = [
        cron(renew_mail_watches, hour=3, minute=0),                   # 3am daily
        cron(purge_raw_emails, minute=0),                             # every hour
        cron(cleanup_processed_webhooks, hour=4, minute=0),           # 4am daily
        cron(schedule_connect_syncs, hour={0, 6, 12, 18}, minute=0), # every 6h
        cron(refresh_subscriptions_cache, hour=5, minute=30),         # 5:30am daily
        cron(schedule_plaid_syncs, hour=3, minute=30),                # 3:30am daily
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 20        # High concurrency — these are all I/O bound
    job_timeout = 60     # 1 min max — if it takes longer, something's wrong
    queue_name = "arq:queue"  # Default queue


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
    max_jobs = 5         # Low concurrency — these are CPU/API heavy
    job_timeout = 600    # 10 min — bank scrapes can be slow
    queue_name = "arq:queue:slow"
```

### Step 2: Update `enqueue_job` to route to correct queue

```python
# backend/jobs/queue.py

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
    await redis.enqueue_job(function_name, *args, _queue_name=queue_name, **kwargs)
    await redis.aclose()
```

Note: `schedule_connect_syncs` and `schedule_plaid_syncs` are NOT in `SLOW_JOBS` — they run as cron jobs on the fast worker, not as enqueued jobs.

### Step 3: Railway deployment

Add a second service in Railway:

```
# Existing service: luka-worker
Command: python -m arq worker.FastWorkerSettings

# New service: luka-worker-bg
Command: python -m arq worker.SlowWorkerSettings
```

Both services share the same Redis instance and Supabase database. Railway cost: ~$5/mo extra for the second worker.

### Step 4: Procfile (for local dev)

```procfile
web: uvicorn main:app --host 0.0.0.0 --port $PORT
worker-fast: python -m arq worker.FastWorkerSettings
worker-slow: python -m arq worker.SlowWorkerSettings
```

## Migration Safety

**Deploy order matters.** The old single worker reads from `arq:queue`. If slow jobs are already queued there when the new fast worker (60s timeout) takes over, those jobs will be killed.

1. **Deploy the updated `enqueue_job` routing first** — new slow jobs go to `arq:queue:slow`, fast jobs stay on `arq:queue`
2. **Wait for the old queue to drain** — let the existing single worker finish any in-flight slow jobs (max 5min)
3. **Switch workers** — replace the single `WorkerSettings` with `FastWorkerSettings` + `SlowWorkerSettings` and deploy both services

This is safe because step 1 is backwards-compatible: the old worker ignores `_queue_name` on the consumer side (it reads from its configured queue). New slow jobs will queue up in `arq:queue:slow` until the slow worker is deployed in step 3.

## Scaling Beyond 200 Users

### Horizontal Scaling (500+ users)

Run multiple replicas of each worker:

```
luka-worker      × 2 replicas (max_jobs=20 each → 40 concurrent fast jobs)
luka-worker-bg   × 2 replicas (max_jobs=5 each → 10 concurrent slow jobs)
```

ARQ handles this safely — multiple workers compete for the same Redis queue with atomic BRPOPLPUSH. No duplicate processing.

### LLM Rate Limiting (critical at scale)

`process_merchant_review` calls the LLM for each merchant. At 200 users × 10 merchants each = 2,000 LLM calls during a sync burst.

**Solutions:**
1. **Semaphore in worker**: Limit concurrent LLM calls to 5 across all merchant review jobs
2. **Batch LLM calls**: Group multiple merchants into a single prompt (already done for `group_raw_merchants`, extend to categorization)
3. **Cache aggressively**: If "Starbucks" is categorized once, never call the LLM again for it (canonical merchant DB already does this)

```python
# Example: asyncio.Semaphore for LLM rate limiting
LLM_SEMAPHORE = asyncio.Semaphore(5)

async def lookup_merchant_throttled(name, db, redis):
    async with LLM_SEMAPHORE:
        return await lookup_merchant(name, db, redis)
```

### Database Connection Pooling

At 200 users with 2 workers × 25 max connections each = 50 connections. Supabase free tier allows 60. Options:
- Use PgBouncer (Supabase has it built-in on port 6543)
- Set `pool_size=10` in SQLAlchemy engine config
- Switch to Supabase Pro for 200 connections

### Redis Memory

Each review job stores `transaction_ids` as JSONB. At 200 users × 50 transactions × 36 bytes (UUID string) = ~360KB. Negligible. Redis memory will be dominated by ARQ's job metadata and deduplication keys — still well under 100MB.

## Migration Path

| Phase | Users | Architecture | Monthly Cost |
|-------|-------|-------------|-------------|
| Now | 1-50 | Single worker, single queue | ~$5 |
| Phase 1 | 50-200 | Two workers (fast/slow), same Redis | ~$10 |
| Phase 2 | 200-500 | Two workers × 2 replicas, PgBouncer | ~$20 |
| Phase 3 | 500+ | Dedicated LLM queue, connection pooler, horizontal scaling | ~$40 |

## When to Implement Phase 1

Trigger: any of these symptoms appear:
- Email processing latency > 5s (check via ARQ job durations in logs)
- Merchant review jobs queuing for > 30s before starting
- Worker hitting `max_jobs` regularly (all 10 slots occupied)
- Users reporting delayed notifications

**The implementation is ~2 hours of work**: split WorkerSettings, update enqueue_job routing, add Railway service.
