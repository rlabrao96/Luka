---
source_file: "backend/modules/plaid/sync.py"
type: "rationale"
community: "Plaid & Subscriptions"
location: "L1"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Plaid_&_Subscriptions
---

# Plaid transaction sync: fetches transactions via cursor, creates accounts, maps

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[PlaidItem]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[sync.py]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Plaid_&_Subscriptions