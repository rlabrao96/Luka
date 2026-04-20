---
source_file: "backend/tests/test_contribution_modes.py"
type: "code"
community: "Household Contributions"
location: "L65"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Household_Contributions
---

# _insert_income()

## Connections
- [[Insert a synthetic income transaction inside the wrapping SAVEPOINT.]] - `rationale_for` [EXTRACTED]
- [[Transaction]] - `calls` [INFERRED]
- [[_current_month()]] - `calls` [EXTRACTED]
- [[test_breakdown_never_reads_fixed_member_real_income()]] - `calls` [EXTRACTED]
- [[test_contribution_modes.py]] - `contains` [EXTRACTED]
- [[test_household_view_reimbursement_mode_contributes_zero()]] - `calls` [EXTRACTED]
- [[test_household_view_sums_full_real_plus_fixed_amount()]] - `calls` [EXTRACTED]
- [[test_personal_view_fixed_member_sees_own_real_income()]] - `calls` [EXTRACTED]
- [[test_personal_view_full_member_sees_own_real_income()]] - `calls` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Household_Contributions