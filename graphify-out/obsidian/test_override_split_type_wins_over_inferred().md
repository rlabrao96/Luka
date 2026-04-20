---
source_file: "backend/tests/test_subscription_reclassify.py"
type: "code"
community: "Plaid & Subscriptions"
location: "L325"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Plaid_&_Subscriptions
---

# test_override_split_type_wins_over_inferred()

## Connections
- [[Transaction]] - `calls` [INFERRED]
- [[TransactionSplit]] - `calls` [INFERRED]
- [[_get_seed_household_id()_2]] - `calls` [EXTRACTED]
- [[_get_seed_user()_2]] - `calls` [EXTRACTED]
- [[get_detected_subscriptions()]] - `calls` [INFERRED]
- [[test_subscription_reclassify.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Plaid_&_Subscriptions