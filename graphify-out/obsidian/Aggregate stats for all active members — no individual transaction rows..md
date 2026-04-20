---
source_file: "backend/modules/households/service.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L455"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Aggregate stats for all active members — no individual transaction rows.

## Connections
- [[Household]] - `uses` [INFERRED]
- [[HouseholdInvite]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[get_member_stats()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation