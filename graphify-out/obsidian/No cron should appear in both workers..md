---
source_file: "backend/tests/test_worker_settings.py"
type: "rationale"
community: "ARQ Worker Config"
location: "L68"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/ARQ_Worker_Config
---

# No cron should appear in both workers.

## Connections
- [[FastWorkerSettings]] - `uses` [INFERRED]
- [[SlowWorkerSettings]] - `uses` [INFERRED]
- [[test_no_cron_overlap()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/ARQ_Worker_Config