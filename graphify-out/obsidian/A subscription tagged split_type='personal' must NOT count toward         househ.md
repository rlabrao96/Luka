---
source_file: "backend/tests/test_subscription_reclassify.py"
type: "rationale"
community: "Plaid & Subscriptions"
location: "L437"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Plaid_&_Subscriptions
---

# A subscription tagged split_type='personal' must NOT count toward         househ

## Connections
- [[SubscriptionOverrideRequest]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Plaid_&_Subscriptions