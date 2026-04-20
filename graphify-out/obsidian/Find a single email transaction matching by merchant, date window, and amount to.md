---
source_file: "backend/modules/reconciliation/dedup.py"
type: "rationale"
community: "Plaid & Subscriptions"
location: "L130"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Plaid_&_Subscriptions
---

# Find a single email transaction matching by merchant, date window, and amount to

## Connections
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[_find_single_match()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Plaid_&_Subscriptions