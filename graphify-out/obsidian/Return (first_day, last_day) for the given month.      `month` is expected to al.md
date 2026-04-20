---
source_file: "backend/modules/budgets/cuota_service.py"
type: "rationale"
community: "Cuotas (Installments)"
location: "L24"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Cuotas_(Installments)
---

# Return (first_day, last_day) for the given month.      `month` is expected to al

## Connections
- [[CuotaPurchase]] - `uses` [INFERRED]
- [[_month_bounds()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Cuotas_(Installments)