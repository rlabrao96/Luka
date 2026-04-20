---
source_file: "backend/modules/budgets/forecast.py"
type: "code"
community: "Budgets (v2 v3)"
location: "L149"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Budgets_(v2_v3)
---

# spendable_ceiling()

## Connections
- [[.test_personal_allocation_default_is_zero()]] - `calls` [INFERRED]
- [[.test_personal_allocation_overspent_clamps_to_zero()]] - `calls` [INFERRED]
- [[.test_personal_allocation_subtracts_from_spendable()]] - `calls` [INFERRED]
- [[Discretionary budget = income minus fixed commitments.      Clamped to 0 — a neg]] - `rationale_for` [EXTRACTED]
- [[forecast.py]] - `contains` [EXTRACTED]
- [[get_budget_v2()]] - `calls` [INFERRED]
- [[test_spendable_ceiling_basic()]] - `calls` [INFERRED]
- [[test_spendable_ceiling_clamped_to_zero()]] - `calls` [INFERRED]
- [[test_spendable_ceiling_decimal_precision()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Budgets_(v2_v3)