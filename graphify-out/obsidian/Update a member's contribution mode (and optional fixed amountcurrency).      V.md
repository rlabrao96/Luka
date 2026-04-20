---
source_file: "backend/modules/households/contribution_service.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L322"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Update a member's contribution mode (and optional fixed amount/currency).      V

## Connections
- [[HouseholdMember]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[update_contribution()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation