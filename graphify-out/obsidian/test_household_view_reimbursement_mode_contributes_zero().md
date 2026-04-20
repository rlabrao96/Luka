---
source_file: "backend/tests/test_contribution_modes.py"
type: "code"
community: "Household Contributions"
location: "L150"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Household_Contributions
---

# test_household_view_reimbursement_mode_contributes_zero()

## Connections
- [[HOGAR REIMB rafa is `full`, partner is `reimbursement`.      Even though partne]] - `rationale_for` [EXTRACTED]
- [[_current_month()]] - `calls` [EXTRACTED]
- [[_household_by_name()]] - `calls` [EXTRACTED]
- [[_insert_income()]] - `calls` [EXTRACTED]
- [[_user_by_email()]] - `calls` [EXTRACTED]
- [[income_for_household_view()]] - `calls` [INFERRED]
- [[test_contribution_modes.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Household_Contributions