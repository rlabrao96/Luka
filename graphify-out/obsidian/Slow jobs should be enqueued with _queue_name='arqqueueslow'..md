---
source_file: "backend/tests/test_queue_routing.py"
type: "rationale"
community: "Backend Core & Infra"
location: "L27"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/Backend_Core_&_Infra
---

# Slow jobs should be enqueued with _queue_name='arq:queue:slow'.

## Connections
- [[test_enqueue_slow_job_routes_to_slow_queue()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/EXTRACTED #community/Backend_Core_&_Infra