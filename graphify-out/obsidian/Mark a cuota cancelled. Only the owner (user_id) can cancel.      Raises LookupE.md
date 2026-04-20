---
source_file: "backend/modules/budgets/cuota_service.py"
type: "rationale"
community: "Cuotas (Installments)"
location: "L208"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Cuotas_(Installments)
---

# Mark a cuota cancelled. Only the owner (user_id) can cancel.      Raises LookupE

## Connections
- [[CuotaPurchase]] - `uses` [INFERRED]
- [[cancel_cuota()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Cuotas_(Installments)