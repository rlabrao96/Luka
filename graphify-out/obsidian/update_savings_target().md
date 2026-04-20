---
source_file: "backend/modules/budgets/user_budget_settings_service.py"
type: "code"
community: "User Budget Settings"
location: "L39"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/User_Budget_Settings
---

# update_savings_target()

## Connections
- [[Set the caller's monthly savings target and its currency.      Passing `amount=N]] - `rationale_for` [EXTRACTED]
- [[get_or_create()]] - `calls` [EXTRACTED]
- [[patch_budget_settings()]] - `calls` [INFERRED]
- [[test_get_savings_target_currency_mismatch_returns_zero()]] - `calls` [INFERRED]
- [[test_update_savings_target_persists()]] - `calls` [INFERRED]
- [[user_budget_settings_service.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/User_Budget_Settings