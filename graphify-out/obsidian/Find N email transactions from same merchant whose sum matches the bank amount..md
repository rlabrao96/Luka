---
source_file: "backend/modules/reconciliation/dedup.py"
type: "rationale"
community: "Plaid & Subscriptions"
location: "L171"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Plaid_&_Subscriptions
---

# Find N email transactions from same merchant whose sum matches the bank amount.

## Connections
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[_find_sum_match()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Plaid_&_Subscriptions