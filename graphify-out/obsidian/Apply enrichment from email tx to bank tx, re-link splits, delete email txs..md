---
source_file: "backend/modules/reconciliation/dedup.py"
type: "rationale"
community: "Plaid & Subscriptions"
location: "L94"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Plaid_&_Subscriptions
---

# Apply enrichment from email tx to bank tx, re-link splits, delete email txs.

## Connections
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[apply_match_and_delete_emails()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Plaid_&_Subscriptions