---
source_file: "backend/modules/households/service.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L203"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Return non-accepted, non-expired invites.

## Connections
- [[Household]] - `uses` [INFERRED]
- [[HouseholdInvite]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[get_pending_invites()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation