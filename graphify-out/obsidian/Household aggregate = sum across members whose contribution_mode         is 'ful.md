---
source_file: "backend/tests/test_user_budget_settings.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L132"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Household aggregate = sum across members whose contribution_mode         is 'ful

## Connections
- [[User]] - `uses` [INFERRED]
- [[UserBudgetSettings]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation