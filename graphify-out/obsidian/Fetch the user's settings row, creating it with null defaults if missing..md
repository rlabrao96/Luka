---
source_file: "backend/modules/budgets/user_budget_settings_service.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L28"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Fetch the user's settings row, creating it with null defaults if missing.

## Connections
- [[HouseholdMember]] - `uses` [INFERRED]
- [[UserBudgetSettings]] - `uses` [INFERRED]
- [[get_or_create()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation