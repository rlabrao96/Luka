---
source_file: "backend/modules/budgets/user_budget_settings_service.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L109"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Sum savings targets across active household members in the given currency.

## Connections
- [[HouseholdMember]] - `uses` [INFERRED]
- [[UserBudgetSettings]] - `uses` [INFERRED]
- [[get_household_savings_target()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation