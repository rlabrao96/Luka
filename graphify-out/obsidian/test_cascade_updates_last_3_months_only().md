---
source_file: "backend/tests/test_subscription_reclassify.py"
type: "code"
community: "Plaid & Subscriptions"
location: "L153"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Plaid_&_Subscriptions
---

# test_cascade_updates_last_3_months_only()

## Connections
- [[Transaction]] - `calls` [INFERRED]
- [[TransactionSplit]] - `calls` [INFERRED]
- [[_get_seed_household_id()_2]] - `calls` [EXTRACTED]
- [[_get_seed_user()_2]] - `calls` [EXTRACTED]
- [[reclassify_subscription_split()]] - `calls` [INFERRED]
- [[test_subscription_reclassify.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Plaid_&_Subscriptions