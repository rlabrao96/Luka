---
source_file: "backend/modules/plaid/sync.py"
type: "rationale"
community: "Plaid & Subscriptions"
location: "L21"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Plaid_&_Subscriptions
---

# Run a full sync for a Plaid item. Returns stats dict.

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[PlaidItem]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[run_plaid_sync()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Plaid_&_Subscriptions