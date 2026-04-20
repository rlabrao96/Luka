---
source_file: "backend/tests/test_worker_settings.py"
type: "rationale"
community: "ARQ Worker Config"
location: "L1"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/ARQ_Worker_Config
---

# Test that worker settings assign jobs and crons to the correct worker.

## Connections
- [[FastWorkerSettings]] - `uses` [INFERRED]
- [[SlowWorkerSettings]] - `uses` [INFERRED]
- [[test_worker_settings.py]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/ARQ_Worker_Config