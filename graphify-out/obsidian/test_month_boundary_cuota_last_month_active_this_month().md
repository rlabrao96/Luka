---
source_file: "backend/tests/test_cuota_service.py"
type: "code"
community: "Cuotas (Installments)"
location: "L98"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Cuotas_(Installments)
---

# test_month_boundary_cuota_last_month_active_this_month()

## Connections
- [[A cuota starting last month and ending this month counts as active for both.]] - `rationale_for` [EXTRACTED]
- [[_get_first_household_id()]] - `calls` [EXTRACTED]
- [[_get_seed_user()_3]] - `calls` [EXTRACTED]
- [[create_cuota()]] - `calls` [INFERRED]
- [[get_active_cuotas_summary()]] - `calls` [INFERRED]
- [[test_cuota_service.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Cuotas_(Installments)