---
source_file: "backend/modules/budgets/cuota_router.py"
type: "rationale"
community: "Cuotas (Installments)"
location: "L105"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Cuotas_(Installments)
---

# Cancel a cuota. Returns {"ok": true} on success.      Returns a JSON body (not 2

## Connections
- [[CuotaCreateRequest]] - `uses` [INFERRED]
- [[CuotaListResponse]] - `uses` [INFERRED]
- [[CuotaResponse]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[delete_cuota()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Cuotas_(Installments)