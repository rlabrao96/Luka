---
source_file: "backend/tests/test_budget_v3_sankey.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L422"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Yield every leaf value in a nested dict/list structure.

## Connections
- [[Household]] - `uses` [INFERRED]
- [[HouseholdIncomeBreakdown]] - `uses` [INFERRED]
- [[OtherMemberContribution]] - `uses` [INFERRED]
- [[SankeyNode]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[_walk_json_values()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation