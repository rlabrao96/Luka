---
source_file: "backend/tests/test_cuota_service.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L99"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# A cuota starting last month and ending this month counts as active for both.

## Connections
- [[HouseholdMember]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[test_month_boundary_cuota_last_month_active_this_month()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation