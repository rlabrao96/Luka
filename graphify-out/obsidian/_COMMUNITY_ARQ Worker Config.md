---
type: community
cohesion: 0.15
members: 21
---

# ARQ Worker Config

**Cohesion:** 0.15 - loosely connected
**Members:** 21 nodes

## Members
- [[FastWorkerSettings]] - code - backend/worker.py
- [[Handles bank syncs, LLM processing, and heavy batch jobs.]] - rationale - backend/worker.py
- [[Handles webhooks, emails, schedulers, and lightweight cron jobs.]] - rationale - backend/worker.py
- [[No cron should appear in both workers.]] - rationale - backend/tests/test_worker_settings.py
- [[No function should appear in both workers.]] - rationale - backend/tests/test_worker_settings.py
- [[SlowWorkerSettings]] - code - backend/worker.py
- [[Test that worker settings assign jobs and crons to the correct worker.]] - rationale - backend/tests/test_worker_settings.py
- [[_cron_names()]] - code - backend/tests/test_worker_settings.py
- [[_func_names()]] - code - backend/tests/test_worker_settings.py
- [[shutdown()]] - code - backend/worker.py
- [[startup()]] - code - backend/worker.py
- [[test_fast_worker_config()]] - code - backend/tests/test_worker_settings.py
- [[test_fast_worker_cron_jobs()]] - code - backend/tests/test_worker_settings.py
- [[test_fast_worker_functions()]] - code - backend/tests/test_worker_settings.py
- [[test_no_cron_overlap()]] - code - backend/tests/test_worker_settings.py
- [[test_no_job_overlap()]] - code - backend/tests/test_worker_settings.py
- [[test_slow_worker_config()]] - code - backend/tests/test_worker_settings.py
- [[test_slow_worker_cron_jobs()]] - code - backend/tests/test_worker_settings.py
- [[test_slow_worker_functions()]] - code - backend/tests/test_worker_settings.py
- [[test_worker_settings.py]] - code - backend/tests/test_worker_settings.py
- [[worker.py]] - code - backend/worker.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/ARQ_Worker_Config
SORT file.name ASC
```
