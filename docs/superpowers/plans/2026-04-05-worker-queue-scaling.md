# Worker Queue Scaling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the single ARQ worker into fast/slow workers with separate queues so email webhooks are never blocked by bank syncs or LLM jobs.

**Architecture:** Add queue routing to `enqueue_job` (SLOW_JOBS set → `arq:queue:slow`), split `WorkerSettings` into `FastWorkerSettings` + `SlowWorkerSettings`, deploy a second Railway service for the slow worker.

**Tech Stack:** ARQ (async Redis queue), Railway CLI, Python 3.12

**Spec:** `docs/superpowers/specs/2026-04-04-worker-queue-scaling.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/jobs/queue.py` | Modify | Add `SLOW_JOBS` set + `_queue_name` routing |
| `backend/worker.py` | Modify | Split `WorkerSettings` → `FastWorkerSettings` + `SlowWorkerSettings` |
| `backend/Procfile` | Modify | Add `worker-slow` entry for local dev |
| `backend/tests/test_queue_routing.py` | Create | Test that job routing picks correct queue |
| `backend/tests/test_worker_settings.py` | Create | Test that worker settings have correct job/cron assignments |

---

### Task 1: Add queue routing to `enqueue_job`

**Files:**
- Modify: `backend/jobs/queue.py`
- Create: `backend/tests/test_queue_routing.py`

This is the backwards-compatible change that gets deployed first (Migration Safety step 1).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_queue_routing.py`:

```python
"""Test that enqueue_job routes jobs to the correct queue."""
import pytest
from unittest.mock import AsyncMock, patch

from jobs.queue import SLOW_JOBS, enqueue_job


def test_slow_jobs_set_contains_expected_jobs():
    """SLOW_JOBS should contain exactly the heavy jobs."""
    assert SLOW_JOBS == {
        "run_connect_sync",
        "run_plaid_sync_job",
        "process_merchant_review",
        "run_reconciliation_job",
    }


def test_slow_jobs_does_not_contain_schedulers():
    """Schedulers are lightweight cron jobs — they must NOT be in SLOW_JOBS."""
    assert "schedule_connect_syncs" not in SLOW_JOBS
    assert "schedule_plaid_syncs" not in SLOW_JOBS


@pytest.mark.asyncio
async def test_enqueue_slow_job_routes_to_slow_queue():
    """Slow jobs should be enqueued with _queue_name='arq:queue:slow'."""
    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock()

    with patch("jobs.queue.create_pool", return_value=mock_pool):
        await enqueue_job("run_connect_sync", "cred-123")

    mock_pool.enqueue_job.assert_called_once_with(
        "run_connect_sync", "cred-123", _queue_name="arq:queue:slow"
    )


@pytest.mark.asyncio
async def test_enqueue_fast_job_routes_to_default_queue():
    """Fast jobs should be enqueued with _queue_name='arq:queue'."""
    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock()

    with patch("jobs.queue.create_pool", return_value=mock_pool):
        await enqueue_job("process_email", "gmail", email_address="user@test.com")

    mock_pool.enqueue_job.assert_called_once_with(
        "process_email", "gmail", email_address="user@test.com", _queue_name="arq:queue"
    )


@pytest.mark.asyncio
async def test_enqueue_unknown_job_routes_to_fast_queue():
    """Unknown job names default to the fast queue."""
    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock()

    with patch("jobs.queue.create_pool", return_value=mock_pool):
        await enqueue_job("some_future_job", "arg1")

    mock_pool.enqueue_job.assert_called_once_with(
        "some_future_job", "arg1", _queue_name="arq:queue"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_queue_routing.py -v`
Expected: FAIL — `SLOW_JOBS` not defined yet in `queue.py`

- [ ] **Step 3: Implement queue routing**

Update `backend/jobs/queue.py` to:

```python
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
    try:
        await redis.enqueue_job(function_name, *args, _queue_name=queue_name, **kwargs)
    finally:
        await redis.aclose()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_queue_routing.py -v`
Expected: All 5 tests PASS

- [ ] **Step 4b: Run full test suite to check nothing broke**

Run: `cd backend && python -m pytest --tb=short -q`
Expected: All existing tests still pass (enqueue_job signature unchanged, callers unaffected)

- [ ] **Step 5: Commit**

```bash
git add backend/jobs/queue.py backend/tests/test_queue_routing.py
git commit -m "feat(worker): add queue routing — slow jobs go to arq:queue:slow"
```

---

### Task 2: Split WorkerSettings into Fast and Slow

**Files:**
- Modify: `backend/worker.py`
- Create: `backend/tests/test_worker_settings.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_worker_settings.py`:

```python
"""Test that worker settings assign jobs and crons to the correct worker."""
from worker import FastWorkerSettings, SlowWorkerSettings


def _func_names(settings_cls):
    return {f.__name__ for f in settings_cls.functions}


def _cron_names(settings_cls):
    return {c.coroutine.__name__ for c in settings_cls.cron_jobs}


def test_fast_worker_functions():
    assert _func_names(FastWorkerSettings) == {
        "process_email",
        "send_invite_email",
    }


def test_slow_worker_functions():
    assert _func_names(SlowWorkerSettings) == {
        "run_connect_sync",
        "run_plaid_sync_job",
        "process_merchant_review",
    }


def test_fast_worker_cron_jobs():
    expected = {
        "renew_mail_watches",
        "purge_raw_emails",
        "cleanup_processed_webhooks",
        "schedule_connect_syncs",
        "refresh_subscriptions_cache",
        "schedule_plaid_syncs",
    }
    assert _cron_names(FastWorkerSettings) == expected


def test_slow_worker_cron_jobs():
    assert _cron_names(SlowWorkerSettings) == {"run_reconciliation_job"}


def test_fast_worker_config():
    assert FastWorkerSettings.max_jobs == 20
    assert FastWorkerSettings.job_timeout == 60
    assert FastWorkerSettings.queue_name == "arq:queue"


def test_slow_worker_config():
    assert SlowWorkerSettings.max_jobs == 5
    assert SlowWorkerSettings.job_timeout == 600
    assert SlowWorkerSettings.queue_name == "arq:queue:slow"


def test_no_job_overlap():
    """No function should appear in both workers."""
    fast = _func_names(FastWorkerSettings)
    slow = _func_names(SlowWorkerSettings)
    assert fast & slow == set()


def test_no_cron_overlap():
    """No cron should appear in both workers."""
    fast = _cron_names(FastWorkerSettings)
    slow = _cron_names(SlowWorkerSettings)
    assert fast & slow == set()


def test_worker_settings_alias():
    """WorkerSettings alias exists for backwards compat during migration."""
    from worker import WorkerSettings
    assert WorkerSettings is FastWorkerSettings
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_worker_settings.py -v`
Expected: FAIL — `FastWorkerSettings` not defined

- [ ] **Step 3: Replace WorkerSettings with Fast + Slow**

Replace the `WorkerSettings` class in `backend/worker.py` with:

```python
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


# Backwards compat: Railway's existing worker service uses `worker.WorkerSettings`
# Remove this alias after both services are deployed (Task 6)
WorkerSettings = FastWorkerSettings
```

Note the `WorkerSettings = FastWorkerSettings` alias — this keeps the existing Railway service running during migration. The old `python -m arq worker.WorkerSettings` command still works, just now it points to the fast config.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_worker_settings.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Run full test suite to check nothing broke**

Run: `cd backend && python -m pytest --tb=short -q`
Expected: All existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add backend/worker.py backend/tests/test_worker_settings.py
git commit -m "feat(worker): split WorkerSettings into Fast + Slow classes"
```

---

### Task 3: Update Procfile for local dev

**Files:**
- Modify: `backend/Procfile`

- [ ] **Step 1: Update Procfile**

Replace `backend/Procfile` contents with:

```procfile
web: uvicorn main:app --host 0.0.0.0 --port $PORT
worker-fast: python -m arq worker.FastWorkerSettings
worker-slow: python -m arq worker.SlowWorkerSettings
```

- [ ] **Step 2: Commit**

```bash
git add backend/Procfile
git commit -m "chore: update Procfile with fast/slow worker entries"
```

---

### Task 4: Pre-deployment verification (CHECKPOINT)

**Purpose:** Verify everything works end-to-end before touching production. This is a human review checkpoint.

- [ ] **Step 1: Run full test suite**

Run: `cd backend && python -m pytest -v --tb=short`
Expected: ALL tests pass — both new (queue routing + worker settings) and existing.

- [ ] **Step 2: Verify worker imports resolve**

Run both workers locally to confirm they start without import errors (they'll fail to connect to Redis, that's fine — we're checking imports):

```bash
cd backend && timeout 5 python -c "from worker import FastWorkerSettings, SlowWorkerSettings; print('FastWorker functions:', [f.__name__ for f in FastWorkerSettings.functions]); print('SlowWorker functions:', [f.__name__ for f in SlowWorkerSettings.functions]); print('FastWorker crons:', [c.coroutine.__name__ for c in FastWorkerSettings.cron_jobs]); print('SlowWorker crons:', [c.coroutine.__name__ for c in SlowWorkerSettings.cron_jobs])"
```

Expected output:
```
FastWorker functions: ['process_email', 'send_invite_email']
SlowWorker functions: ['run_connect_sync', 'run_plaid_sync_job', 'process_merchant_review']
FastWorker crons: ['renew_mail_watches', 'purge_raw_emails', 'cleanup_processed_webhooks', 'schedule_connect_syncs', 'refresh_subscriptions_cache', 'schedule_plaid_syncs']
SlowWorker crons: ['run_reconciliation_job']
```

- [ ] **Step 3: Verify queue routing logic**

```bash
cd backend && python -c "from jobs.queue import SLOW_JOBS; print('SLOW_JOBS:', SLOW_JOBS); print('run_connect_sync is slow:', 'run_connect_sync' in SLOW_JOBS); print('process_email is fast:', 'process_email' not in SLOW_JOBS)"
```

Expected: All three prints confirm correct routing.

- [ ] **Step 4: Verify backwards-compat alias**

```bash
cd backend && python -c "from worker import WorkerSettings, FastWorkerSettings; assert WorkerSettings is FastWorkerSettings; print('WorkerSettings alias OK — safe to deploy')"
```

- [ ] **Step 5: Review git diff before pushing**

```bash
git log --oneline main..HEAD
git diff --stat main
```

Present the diff summary to the user for review before proceeding to deployment.

---

### Task 5: Deploy queue routing (Migration Safety step 1)

**Requires user interaction:** You'll need to run `railway link` to select the project.

This deploys the backwards-compatible routing change. Slow jobs start queuing in `arq:queue:slow` while the old worker continues processing fast jobs normally.

- [ ] **Step 1: Link Railway project**

Run: `railway link`
Select: `Luka` project, `production` environment

- [ ] **Step 2: Push code to trigger redeploy of existing services**

```bash
git push origin main
```

The existing `luka-worker` service will redeploy with the new `enqueue_job` routing. It still runs `worker.WorkerSettings` (now aliased to `FastWorkerSettings`), so it only processes fast queue jobs. New slow jobs queue up in `arq:queue:slow` waiting for the slow worker.

**Note:** Between this deploy and Task 6, slow jobs (bank syncs, merchant reviews) will queue but not process. This is expected. Proceed to Task 6 immediately to minimize the gap.

- [ ] **Step 3: Verify existing worker is healthy**

```bash
railway logs --service luka-worker
```

Check: no errors, cron jobs still firing.

---

### Task 6: Create and deploy slow worker service

- [ ] **Step 1: Create new Railway service for slow worker**

```bash
railway service create luka-worker-bg
```

- [ ] **Step 2: Copy environment variables from existing worker**

The slow worker needs the same env vars (Redis URL, Supabase, LLM keys, etc.):

```bash
railway variables list --service luka-worker --json | railway variables set --service luka-worker-bg
```

If that doesn't work, manually check what vars exist and set them:

```bash
railway variables list --service luka-worker
```

Then set them on the new service. At minimum: `REDIS_URL`, `DATABASE_URL`, `OPENAI_API_KEY` (or whatever LLM key), `BACKEND_PUBLIC_URL`.

- [ ] **Step 3: Configure the slow worker start command**

```bash
railway variables set --service luka-worker-bg RAILWAY_START_COMMAND="python -m arq worker.SlowWorkerSettings"
```

Or configure via the service settings if the CLI doesn't support this directly.

- [ ] **Step 4: Deploy the slow worker**

```bash
railway up --service luka-worker-bg
```

- [ ] **Step 5: Update existing fast worker start command**

Update the existing worker to explicitly use `FastWorkerSettings`:

```bash
railway variables set --service luka-worker RAILWAY_START_COMMAND="python -m arq worker.FastWorkerSettings"
```

- [ ] **Step 6: Verify both workers are running**

```bash
railway logs --service luka-worker
railway logs --service luka-worker-bg
```

Check:
- Fast worker: cron jobs firing (purge, renew, schedule_syncs, etc.)
- Slow worker: `run_reconciliation_job` cron firing, picks up any queued slow jobs

- [ ] **Step 7: Remove WorkerSettings backwards-compat alias**

In `backend/worker.py`, remove the line:
```python
WorkerSettings = FastWorkerSettings
```

Commit and push:
```bash
git add backend/worker.py
git commit -m "chore: remove WorkerSettings alias — both workers now use explicit classes"
git push origin main
```

---

### Task 7: Smoke test the full system

- [ ] **Step 1: Test fast path (email webhook)**

Trigger a Gmail push notification (send yourself a bank email or use the test endpoint). Verify:
- `process_email` runs on the fast worker
- WhatsApp alert arrives
- Fast worker logs show the job

- [ ] **Step 2: Test slow path (bank sync)**

Trigger a bank sync (via dashboard or API). Verify:
- `run_connect_sync` or `run_plaid_sync_job` runs on the slow worker
- `process_merchant_review` runs on the slow worker after sync
- Slow worker logs show the jobs

- [ ] **Step 3: Verify queue isolation**

While a slow job is running, check that the fast worker is still responsive:
```bash
railway logs --service luka-worker
```
Fast worker should show no slow job activity.
