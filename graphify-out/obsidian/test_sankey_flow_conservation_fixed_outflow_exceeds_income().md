---
source_file: "backend/tests/test_budget_v2_endpoint.py"
type: "code"
community: "Budgets (v2 v3)"
location: "L402"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Budgets_(v2_v3)
---

# test_sankey_flow_conservation_fixed_outflow_exceeds_income()

## Connections
- [[Even when income is positive but `known_bills + cuotas + savings_target`     tog]] - `rationale_for` [EXTRACTED]
- [[Transaction]] - `calls` [INFERRED]
- [[UserBudgetSettings]] - `calls` [INFERRED]
- [[_current_month()_2]] - `calls` [EXTRACTED]
- [[_flow_conservation_errors()_1]] - `calls` [EXTRACTED]
- [[_household_by_name()_2]] - `calls` [EXTRACTED]
- [[_user_by_email()_2]] - `calls` [EXTRACTED]
- [[get_budget_v2()]] - `calls` [INFERRED]
- [[test_budget_v2_endpoint.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Budgets_(v2_v3)