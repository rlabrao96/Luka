---
source_file: "backend/tests/test_contribution_modes.py"
type: "code"
community: "Household Contributions"
location: "L186"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Household_Contributions
---

# test_personal_view_fixed_member_sees_own_real_income()

## Connections
- [[_current_month()]] - `calls` [EXTRACTED]
- [[_household_by_name()]] - `calls` [EXTRACTED]
- [[_insert_income()]] - `calls` [EXTRACTED]
- [[_user_by_email()]] - `calls` [EXTRACTED]
- [[income_for_personal_view()]] - `calls` [INFERRED]
- [[partner-fixed in personal view sees their REAL income (not fixed amount).      P]] - `rationale_for` [EXTRACTED]
- [[test_contribution_modes.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Household_Contributions