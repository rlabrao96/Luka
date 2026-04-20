---
source_file: "backend/modules/budgets/user_budget_settings_service.py"
type: "code"
community: "User Budget Settings"
location: "L27"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/User_Budget_Settings
---

# get_or_create()

## Connections
- [[Fetch the user's settings row, creating it with null defaults if missing.]] - `rationale_for` [EXTRACTED]
- [[UserBudgetSettings]] - `calls` [INFERRED]
- [[get_budget_settings()]] - `calls` [INFERRED]
- [[get_payday_day_of_month()]] - `calls` [EXTRACTED]
- [[get_savings_target()]] - `calls` [EXTRACTED]
- [[patch_budget_settings()]] - `calls` [INFERRED]
- [[test_get_or_create_returns_row_with_defaults()]] - `calls` [INFERRED]
- [[test_update_payday_persists_and_validates_range()]] - `calls` [INFERRED]
- [[update_payday()]] - `calls` [EXTRACTED]
- [[update_personal_allocation()]] - `calls` [EXTRACTED]
- [[update_savings_target()]] - `calls` [EXTRACTED]
- [[user_budget_settings_service.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/User_Budget_Settings