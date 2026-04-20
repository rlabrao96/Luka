---
source_file: "backend/tests/test_budget_v3_sankey.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L625"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Every seeded household + currency + view: Sankey flow must be         conservati

## Connections
- [[Household]] - `uses` [INFERRED]
- [[HouseholdIncomeBreakdown]] - `uses` [INFERRED]
- [[OtherMemberContribution]] - `uses` [INFERRED]
- [[SankeyNode]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation