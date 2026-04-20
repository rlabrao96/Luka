---
source_file: "backend/modules/households/contribution_service.py"
type: "code"
community: "Household Contributions"
location: "L119"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Household_Contributions
---

# income_for_household_view()

## Connections
- [[Return household income total, contribution-mode-aware.      Per-member dispatch]] - `rationale_for` [EXTRACTED]
- [[contribution_service.py]] - `contains` [EXTRACTED]
- [[income_for_personal_view()]] - `calls` [EXTRACTED]
- [[test_caller_relative_for_seed_user()]] - `calls` [INFERRED]
- [[test_household_view_reimbursement_mode_contributes_zero()]] - `calls` [INFERRED]
- [[test_household_view_sums_full_real_plus_fixed_amount()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Household_Contributions