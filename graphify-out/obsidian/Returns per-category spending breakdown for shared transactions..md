---
source_file: "backend/modules/households/service.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L302"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Returns per-category spending breakdown for shared transactions.

## Connections
- [[Household]] - `uses` [INFERRED]
- [[HouseholdInvite]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[get_category_breakdown()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation