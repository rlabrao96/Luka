---
source_file: "backend/tests/test_subscription_reclassify.py"
type: "rationale"
community: "Plaid & Subscriptions"
location: "L213"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Plaid_&_Subscriptions
---

# Txns with no existing transaction_splits row get one inserted.

## Connections
- [[SubscriptionOverrideRequest]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Plaid_&_Subscriptions