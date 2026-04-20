---
source_file: "backend/modules/budgets/cuota_service.py"
type: "rationale"
community: "Cuotas (Installments)"
location: "L109"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Cuotas_(Installments)
---

# Add N months to date d, snapping to day=1 semantics.      The cuotas schema enfo

## Connections
- [[CuotaPurchase]] - `uses` [INFERRED]
- [[_add_months()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Cuotas_(Installments)