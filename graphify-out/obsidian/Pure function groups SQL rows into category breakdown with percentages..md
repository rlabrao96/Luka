---
source_file: "backend/modules/households/service.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L263"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Pure function: groups SQL rows into category breakdown with percentages.

## Connections
- [[Household]] - `uses` [INFERRED]
- [[HouseholdInvite]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[build_category_breakdown()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation