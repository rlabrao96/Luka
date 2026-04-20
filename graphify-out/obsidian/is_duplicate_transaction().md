---
source_file: "backend/modules/transactions/service.py"
type: "code"
community: "Transactions API"
location: "L301"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Transactions_API
---

# is_duplicate_transaction()

## Connections
- [[Two-tier dedup for email transactions     1. Same amount + SAME bank within 5 m]] - `rationale_for` [EXTRACTED]
- [[process_email()]] - `calls` [INFERRED]
- [[service.py_5]] - `contains` [EXTRACTED]
- [[test_detects_duplicate_within_5_minutes()]] - `calls` [INFERRED]
- [[test_no_duplicate_when_none_found()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Transactions_API