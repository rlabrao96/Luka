---
source_file: "backend/modules/budgets/cuota_service.py"
type: "code"
community: "Cuotas (Installments)"
location: "L120"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Cuotas_(Installments)
---

# create_cuota()

## Connections
- [[Create a cuota record. Derives monthly_amount and last_cuota_date.      - `month]] - `rationale_for` [EXTRACTED]
- [[CuotaPurchase]] - `calls` [INFERRED]
- [[_add_months()]] - `calls` [EXTRACTED]
- [[cuota_service.py]] - `contains` [EXTRACTED]
- [[post_cuota()]] - `calls` [INFERRED]
- [[test_cancel_cuota_sets_status_cancelled()]] - `calls` [INFERRED]
- [[test_create_cuota_persists_with_computed_fields()]] - `calls` [INFERRED]
- [[test_month_boundary_cuota_last_month_active_this_month()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Cuotas_(Installments)