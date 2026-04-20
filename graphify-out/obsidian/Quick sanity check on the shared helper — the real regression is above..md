---
source_file: "backend/tests/test_contribution_modes.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L235"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Quick sanity check on the shared helper — the real regression is above.

## Connections
- [[Household]] - `uses` [INFERRED]
- [[HouseholdIncomeBreakdown]] - `uses` [INFERRED]
- [[OtherMemberContribution]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[test_walk_json_helper_finds_forbidden_value()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation