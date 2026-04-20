---
source_file: "backend/tests/test_subscription_reclassify.py"
type: "rationale"
community: "Plaid & Subscriptions"
location: "L1"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Plaid_&_Subscriptions
---

# Tests for subscription split_type classification and cascade behavior.

## Connections
- [[SubscriptionOverrideRequest]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[test_subscription_reclassify.py]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Plaid_&_Subscriptions