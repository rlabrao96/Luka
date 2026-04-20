---
source_file: "backend/modules/budgets/cuota_service.py"
type: "rationale"
community: "Cuotas (Installments)"
location: "L133"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Cuotas_(Installments)
---

# Create a cuota record. Derives monthly_amount and last_cuota_date.      - `month

## Connections
- [[CuotaPurchase]] - `uses` [INFERRED]
- [[create_cuota()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Cuotas_(Installments)