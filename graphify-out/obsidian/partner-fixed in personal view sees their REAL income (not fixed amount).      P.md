---
source_file: "backend/tests/test_contribution_modes.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L187"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# partner-fixed in personal view sees their REAL income (not fixed amount).      P

## Connections
- [[Household]] - `uses` [INFERRED]
- [[HouseholdIncomeBreakdown]] - `uses` [INFERRED]
- [[OtherMemberContribution]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[test_personal_view_fixed_member_sees_own_real_income()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation