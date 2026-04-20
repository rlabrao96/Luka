---
source_file: "backend/modules/households/contribution_service.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L180"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Return a caller-relative breakdown of household income for the month.      PRIVA

## Connections
- [[HouseholdMember]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[income_breakdown_for_household_view()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation