---
source_file: "backend/tests/test_budget_v2_endpoint.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L1"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Integration tests for the `/budgets/v2/{household_id}` endpoint.  These hit the

## Connections
- [[BudgetV2Response]] - `uses` [INFERRED]
- [[Household]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[UserBudgetSettings]] - `uses` [INFERRED]
- [[test_budget_v2_endpoint.py]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation