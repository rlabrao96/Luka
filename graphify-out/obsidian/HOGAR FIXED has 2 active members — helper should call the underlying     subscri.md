---
source_file: "backend/tests/test_subscriptions_read.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L22"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# HOGAR FIXED has 2 active members — helper should call the underlying     subscri

## Connections
- [[Household]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[test_get_household_known_bills_sums_across_members()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation