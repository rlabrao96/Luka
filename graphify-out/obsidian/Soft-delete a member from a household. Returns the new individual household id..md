---
source_file: "backend/modules/households/service.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L125"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Soft-delete a member from a household. Returns the new individual household id.

## Connections
- [[Household]] - `uses` [INFERRED]
- [[HouseholdInvite]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[remove_member()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation