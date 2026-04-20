---
source_file: "backend/modules/budgets/v2_service.py"
type: "code"
community: "Budgets (v2 v3)"
location: "L399"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Budgets_(v2_v3)
---

# _pay_first_fit()

## Connections
- [[.test_enough_income_covers_target()]] - `calls` [INFERRED]
- [[.test_partial_income_splits_between_income_and_otras()]] - `calls` [INFERRED]
- [[.test_zero_income_sends_full_target_to_otras()]] - `calls` [INFERRED]
- [[.test_zero_target_returns_zero_zero()]] - `calls` [INFERRED]
- [[First-fit routing primitive used by the Sankey builders.      Pays `target` out]] - `rationale_for` [EXTRACTED]
- [[_build_hogar_sankey()]] - `calls` [EXTRACTED]
- [[_build_personal_sankey()]] - `calls` [EXTRACTED]
- [[v2_service.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Budgets_(v2_v3)