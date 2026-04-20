---
source_file: "backend/tests/test_budget_v3_sankey.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L434"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Return True if forbidden appears as a numeric leaf (float comparison).

## Connections
- [[Household]] - `uses` [INFERRED]
- [[HouseholdIncomeBreakdown]] - `uses` [INFERRED]
- [[OtherMemberContribution]] - `uses` [INFERRED]
- [[SankeyNode]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[_value_present_in_json()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation