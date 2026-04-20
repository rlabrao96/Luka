---
source_file: "backend/tests/test_contribution_modes.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L399"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Privacy regression: fixed-mode member's real income must NEVER appear         in

## Connections
- [[Household]] - `uses` [INFERRED]
- [[HouseholdIncomeBreakdown]] - `uses` [INFERRED]
- [[OtherMemberContribution]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation