---
source_file: "backend/modules/households/contribution_service.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L93"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Return the caller's own real income for the month.      Personal view always sho

## Connections
- [[HouseholdMember]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[income_for_personal_view()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation