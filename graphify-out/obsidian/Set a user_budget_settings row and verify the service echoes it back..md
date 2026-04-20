---
source_file: "backend/tests/test_budget_v2_endpoint.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L302"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Set a user_budget_settings row and verify the service echoes it back.

## Connections
- [[BudgetV2Response]] - `uses` [INFERRED]
- [[Household]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[UserBudgetSettings]] - `uses` [INFERRED]
- [[test_savings_target_reads_from_user_budget_settings()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation