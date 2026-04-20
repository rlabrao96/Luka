---
source_file: "backend/modules/households/contribution_service.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L126"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Return household income total, contribution-mode-aware.      Per-member dispatch

## Connections
- [[HouseholdMember]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[income_for_household_view()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation