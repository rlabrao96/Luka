---
source_file: "backend/modules/budgets/cuota_router.py"
type: "rationale"
community: "Cuotas (Installments)"
location: "L34"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Cuotas_(Installments)
---

# Return the first active household_id for the current user.      Raises 404 if th

## Connections
- [[CuotaCreateRequest]] - `uses` [INFERRED]
- [[CuotaListResponse]] - `uses` [INFERRED]
- [[CuotaResponse]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[_user_active_household_id()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Cuotas_(Installments)