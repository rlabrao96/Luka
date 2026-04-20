---
source_file: "backend/tests/test_subscription_reclassify.py"
type: "code"
community: "Plaid & Subscriptions"
location: "L507"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Plaid_&_Subscriptions
---

# test_reimbursement_member_personal_bill_does_not_under_count_household()

## Connections
- [[Transaction]] - `calls` [INFERRED]
- [[TransactionSplit]] - `calls` [INFERRED]
- [[_get_seed_household_id()_2]] - `calls` [EXTRACTED]
- [[_get_seed_user()_2]] - `calls` [EXTRACTED]
- [[get_user_personal_known_bills()]] - `calls` [INFERRED]
- [[get_user_shared_known_bills()]] - `calls` [INFERRED]
- [[test_subscription_reclassify.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Plaid_&_Subscriptions