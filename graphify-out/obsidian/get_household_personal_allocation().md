---
source_file: "backend/modules/budgets/user_budget_settings_service.py"
type: "code"
community: "User Budget Settings"
location: "L167"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/User_Budget_Settings
---

# get_household_personal_allocation()

## Connections
- [[Sum personal_allocation_amount across members whose contribution_mode     is 'fu]] - `rationale_for` [EXTRACTED]
- [[get_budget_v2()]] - `calls` [INFERRED]
- [[test_household_personal_allocation_sums_full_and_fixed_members()]] - `calls` [INFERRED]
- [[user_budget_settings_service.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/User_Budget_Settings