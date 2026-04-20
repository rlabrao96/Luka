---
source_file: "backend/modules/transactions/idempotency.py"
type: "rationale"
community: "Backend Core & Infra"
location: "L10"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Backend_Core_&_Infra
---

# Return True if this webhook message was already processed (idempotency check).

## Connections
- [[ProcessedWebhook]] - `uses` [INFERRED]
- [[is_already_processed()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Backend_Core_&_Infra