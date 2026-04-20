---
source_file: "backend/modules/budgets/user_budget_settings_service.py"
type: "code"
community: "User Budget Settings"
location: "L95"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/User_Budget_Settings
---

# get_savings_target()

## Connections
- [[Return the user's savings target in the requested currency, or 0 if mismatch.]] - `rationale_for` [EXTRACTED]
- [[_personal_savings_target()]] - `calls` [INFERRED]
- [[get_household_savings_target()]] - `calls` [EXTRACTED]
- [[get_or_create()]] - `calls` [EXTRACTED]
- [[test_get_savings_target_currency_mismatch_returns_zero()]] - `calls` [INFERRED]
- [[test_update_savings_target_persists()]] - `calls` [INFERRED]
- [[user_budget_settings_service.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/User_Budget_Settings