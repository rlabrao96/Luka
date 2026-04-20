---
source_file: "backend/modules/bank_connect/scheduler.py"
type: "rationale"
community: "Luka Connect & Merchant Review"
location: "L10"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Luka_Connect_&_Merchant_Review
---

# Find all credentials due for sync (next_sync_at <= now).

## Connections
- [[BankCredential]] - `uses` [INFERRED]
- [[get_due_syncs()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Luka_Connect_&_Merchant_Review