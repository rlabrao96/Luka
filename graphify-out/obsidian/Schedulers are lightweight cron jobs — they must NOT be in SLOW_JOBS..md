---
source_file: "backend/tests/test_queue_routing.py"
type: "rationale"
community: "Backend Core & Infra"
location: "L20"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/Backend_Core_&_Infra
---

# Schedulers are lightweight cron jobs — they must NOT be in SLOW_JOBS.

## Connections
- [[test_slow_jobs_does_not_contain_schedulers()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/EXTRACTED #community/Backend_Core_&_Infra