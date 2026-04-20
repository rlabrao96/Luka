---
source_file: "backend/tests/test_cross_sender_dedup.py"
type: "code"
community: "Transactions API"
location: "L9"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Transactions_API
---

# test_detects_duplicate_within_5_minutes()

## Connections
- [[Same amount + within 5 minutes of created_at → duplicate.]] - `rationale_for` [EXTRACTED]
- [[is_duplicate_transaction()]] - `calls` [INFERRED]
- [[test_cross_sender_dedup.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Transactions_API