---
source_file: "backend/modules/households/contribution_service.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L1"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Contribution mode service.  Owns the logic that decides how each household membe

## Connections
- [[HouseholdMember]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[contribution_service.py]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation