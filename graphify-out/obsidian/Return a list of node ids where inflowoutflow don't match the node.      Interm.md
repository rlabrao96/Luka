---
source_file: "backend/tests/test_budget_v2_endpoint.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L345"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Return a list of node ids where inflow/outflow don't match the node.      Interm

## Connections
- [[BudgetV2Response]] - `uses` [INFERRED]
- [[Household]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[UserBudgetSettings]] - `uses` [INFERRED]
- [[_flow_conservation_errors()_1]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation