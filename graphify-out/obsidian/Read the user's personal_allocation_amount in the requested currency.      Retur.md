---
source_file: "backend/modules/budgets/user_budget_settings_service.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L141"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Read the user's personal_allocation_amount in the requested currency.      Retur

## Connections
- [[HouseholdMember]] - `uses` [INFERRED]
- [[UserBudgetSettings]] - `uses` [INFERRED]
- [[get_personal_allocation()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation