---
source_file: "backend/modules/reconciliation/dedup.py"
type: "rationale"
community: "Plaid & Subscriptions"
location: "L214"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Plaid_&_Subscriptions
---

# Extract enrichment data from an email transaction.

## Connections
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[_extract_enrichment()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Plaid_&_Subscriptions