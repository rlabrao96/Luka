---
source_file: "backend/tests/test_contribution_modes.py"
type: "code"
community: "Household Contributions"
location: "L398"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Household_Contributions
---

# test_breakdown_never_reads_fixed_member_real_income()

## Connections
- [[_current_month()]] - `calls` [EXTRACTED]
- [[_household_by_name()]] - `calls` [EXTRACTED]
- [[_insert_income()]] - `calls` [EXTRACTED]
- [[_user_by_email()]] - `calls` [EXTRACTED]
- [[assert_value_absent()]] - `calls` [INFERRED]
- [[income_breakdown_for_household_view()]] - `calls` [INFERRED]
- [[test_contribution_modes.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Household_Contributions