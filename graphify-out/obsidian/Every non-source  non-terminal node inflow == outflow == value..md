---
source_file: "backend/tests/test_budget_v3_sankey.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L197"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Every non-source / non-terminal node: inflow == outflow == value.

## Connections
- [[.test_flow_conservation_each_intermediate()]] - `rationale_for` [EXTRACTED]
- [[Household]] - `uses` [INFERRED]
- [[HouseholdIncomeBreakdown]] - `uses` [INFERRED]
- [[OtherMemberContribution]] - `uses` [INFERRED]
- [[SankeyNode]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation