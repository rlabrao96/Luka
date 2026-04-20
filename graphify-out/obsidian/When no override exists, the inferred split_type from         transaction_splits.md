---
source_file: "backend/tests/test_subscription_reclassify.py"
type: "rationale"
community: "Plaid & Subscriptions"
location: "L384"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Plaid_&_Subscriptions
---

# When no override exists, the inferred split_type from         transaction_splits

## Connections
- [[SubscriptionOverrideRequest]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Plaid_&_Subscriptions