---
source_file: "backend/tests/test_cross_sender_dedup.py"
type: "rationale"
community: "Transactions API"
location: "L10"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/Transactions_API
---

# Same amount + within 5 minutes of created_at → duplicate.

## Connections
- [[test_detects_duplicate_within_5_minutes()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/EXTRACTED #community/Transactions_API