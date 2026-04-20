---
type: community
cohesion: 0.14
members: 31
---

# User Budget Settings

**Cohesion:** 0.14 - loosely connected
**Members:** 31 nodes

## Members
- [[BudgetSettingsRequest]] - code - backend/modules/budgets/user_budget_settings_router.py
- [[BudgetSettingsResponse]] - code - backend/modules/budgets/user_budget_settings_router.py
- [[GET  PATCH settingsbudget — savings target + payday day-of-month.  Thin layer]] - rationale - backend/modules/budgets/user_budget_settings_router.py
- [[_get_seed_household_id()_1]] - code - backend/tests/test_user_budget_settings.py
- [[_get_seed_user()_1]] - code - backend/tests/test_user_budget_settings.py
- [[_household_savings_target()]] - code - backend/modules/budgets/v2_service.py
- [[_personal_savings_target()]] - code - backend/modules/budgets/v2_service.py
- [[_user()]] - code - backend/tests/test_user_budget_settings.py
- [[get_budget_settings()]] - code - backend/modules/budgets/user_budget_settings_router.py
- [[get_household_personal_allocation()]] - code - backend/modules/budgets/user_budget_settings_service.py
- [[get_household_savings_target()]] - code - backend/modules/budgets/user_budget_settings_service.py
- [[get_or_create()]] - code - backend/modules/budgets/user_budget_settings_service.py
- [[get_payday_day_of_month()]] - code - backend/modules/budgets/user_budget_settings_service.py
- [[get_personal_allocation()]] - code - backend/modules/budgets/user_budget_settings_service.py
- [[get_savings_target()]] - code - backend/modules/budgets/user_budget_settings_service.py
- [[patch_budget_settings()]] - code - backend/modules/budgets/user_budget_settings_router.py
- [[test_get_or_create_returns_row_with_defaults()]] - code - backend/tests/test_user_budget_settings.py
- [[test_get_personal_allocation_ignores_wrong_currency()]] - code - backend/tests/test_user_budget_settings.py
- [[test_get_personal_allocation_returns_stored_value()]] - code - backend/tests/test_user_budget_settings.py
- [[test_get_personal_allocation_returns_zero_when_unset()]] - code - backend/tests/test_user_budget_settings.py
- [[test_get_savings_target_currency_mismatch_returns_zero()]] - code - backend/tests/test_user_budget_settings.py
- [[test_household_personal_allocation_sums_full_and_fixed_members()]] - code - backend/tests/test_user_budget_settings.py
- [[test_update_payday_persists_and_validates_range()]] - code - backend/tests/test_user_budget_settings.py
- [[test_update_personal_allocation_persists_and_clears()]] - code - backend/tests/test_user_budget_settings.py
- [[test_update_savings_target_persists()]] - code - backend/tests/test_user_budget_settings.py
- [[test_user_budget_settings.py]] - code - backend/tests/test_user_budget_settings.py
- [[update_payday()]] - code - backend/modules/budgets/user_budget_settings_service.py
- [[update_personal_allocation()]] - code - backend/modules/budgets/user_budget_settings_service.py
- [[update_savings_target()]] - code - backend/modules/budgets/user_budget_settings_service.py
- [[user_budget_settings_router.py]] - code - backend/modules/budgets/user_budget_settings_router.py
- [[user_budget_settings_service.py]] - code - backend/modules/budgets/user_budget_settings_service.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/User_Budget_Settings
SORT file.name ASC
```

## Connections to other communities
- 17 edges to [[_COMMUNITY_DB, Accounts & Allocation]]
- 6 edges to [[_COMMUNITY_Budgets (v2 v3)]]
- 2 edges to [[_COMMUNITY_Pydantic Schemas]]

## Top bridge nodes
- [[BudgetSettingsResponse]] - degree 5, connects to 2 communities
- [[_personal_savings_target()]] - degree 4, connects to 2 communities
- [[_household_savings_target()]] - degree 4, connects to 2 communities
- [[get_payday_day_of_month()]] - degree 4, connects to 2 communities
- [[get_household_personal_allocation()]] - degree 4, connects to 2 communities