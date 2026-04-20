---
source_file: "backend/tests/test_budget_v2_endpoint.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L150"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# rafa-fixed has both CLP and USD txns — both must surface in the picker.

## Connections
- [[BudgetV2Response]] - `uses` [INFERRED]
- [[Household]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[UserBudgetSettings]] - `uses` [INFERRED]
- [[test_hogar_fixed_currencies_available()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation