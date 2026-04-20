---
source_file: "backend/modules/budgets/user_budget_settings_service.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L96"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Return the user's savings target in the requested currency, or 0 if mismatch.

## Connections
- [[HouseholdMember]] - `uses` [INFERRED]
- [[UserBudgetSettings]] - `uses` [INFERRED]
- [[get_savings_target()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation