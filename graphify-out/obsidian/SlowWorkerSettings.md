---
source_file: "backend/worker.py"
type: "code"
community: "ARQ Worker Config"
location: "L57"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/ARQ_Worker_Config
---

# SlowWorkerSettings

## Connections
- [[Handles bank syncs, LLM processing, and heavy batch jobs.]] - `rationale_for` [EXTRACTED]
- [[No cron should appear in both workers.]] - `uses` [INFERRED]
- [[No function should appear in both workers.]] - `uses` [INFERRED]
- [[Test that worker settings assign jobs and crons to the correct worker.]] - `uses` [INFERRED]
- [[worker.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/ARQ_Worker_Config