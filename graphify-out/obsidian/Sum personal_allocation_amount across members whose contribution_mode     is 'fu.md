---
source_file: "backend/modules/budgets/user_budget_settings_service.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L173"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Sum personal_allocation_amount across members whose contribution_mode     is 'fu

## Connections
- [[HouseholdMember]] - `uses` [INFERRED]
- [[UserBudgetSettings]] - `uses` [INFERRED]
- [[get_household_personal_allocation()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation