---
source_file: "backend/modules/budgets/cuota_service.py"
type: "code"
community: "Cuotas (Installments)"
location: "L202"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Cuotas_(Installments)
---

# cancel_cuota()

## Connections
- [[Mark a cuota cancelled. Only the owner (user_id) can cancel.      Raises LookupE]] - `rationale_for` [EXTRACTED]
- [[cuota_service.py]] - `contains` [EXTRACTED]
- [[delete_cuota()]] - `calls` [INFERRED]
- [[test_cancel_cuota_sets_status_cancelled()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Cuotas_(Installments)