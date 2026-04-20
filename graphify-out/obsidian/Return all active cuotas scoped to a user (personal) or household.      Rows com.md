---
source_file: "backend/modules/budgets/cuota_service.py"
type: "rationale"
community: "Cuotas (Installments)"
location: "L180"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Cuotas_(Installments)
---

# Return all active cuotas scoped to a user (personal) or household.      Rows com

## Connections
- [[CuotaPurchase]] - `uses` [INFERRED]
- [[list_active_cuotas()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Cuotas_(Installments)