---
source_file: "backend/modules/reconciliation/dedup.py"
type: "rationale"
community: "Plaid & Subscriptions"
location: "L1"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Plaid_&_Subscriptions
---

# Shared email dedup-and-enrich logic for both Plaid and luka-connect sync.  When

## Connections
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[dedup.py]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Plaid_&_Subscriptions