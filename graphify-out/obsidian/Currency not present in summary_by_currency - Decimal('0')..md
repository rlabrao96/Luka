---
source_file: "backend/tests/test_subscriptions_read.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L90"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Currency not present in summary_by_currency -> Decimal('0').

## Connections
- [[Household]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[test_get_user_known_bills_returns_zero_on_missing_currency()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation