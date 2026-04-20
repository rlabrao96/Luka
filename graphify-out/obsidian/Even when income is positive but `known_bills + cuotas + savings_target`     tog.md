---
source_file: "backend/tests/test_budget_v2_endpoint.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L403"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Even when income is positive but `known_bills + cuotas + savings_target`     tog

## Connections
- [[BudgetV2Response]] - `uses` [INFERRED]
- [[Household]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[UserBudgetSettings]] - `uses` [INFERRED]
- [[test_sankey_flow_conservation_fixed_outflow_exceeds_income()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation