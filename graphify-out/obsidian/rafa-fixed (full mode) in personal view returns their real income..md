---
source_file: "backend/tests/test_contribution_modes.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L212"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# rafa-fixed (full mode) in personal view returns their real income.

## Connections
- [[Household]] - `uses` [INFERRED]
- [[HouseholdIncomeBreakdown]] - `uses` [INFERRED]
- [[OtherMemberContribution]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[test_personal_view_full_member_sees_own_real_income()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation