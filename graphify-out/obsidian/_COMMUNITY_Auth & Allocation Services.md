---
type: community
cohesion: 0.03
members: 97
---

# Auth & Allocation Services

**Cohesion:** 0.03 - loosely connected
**Members:** 97 nodes

## Members
- [[3 members, equal split. One paid everything, other two owe.]] - rationale - backend/tests/test_household_settlement.py
- [[4 members with equal ratio, multiple transfers needed.]] - rationale - backend/tests/test_household_settlement.py
- [[All members paid zero — no transfers needed.]] - rationale - backend/tests/test_household_settlement.py
- [[Attempting to insert a second active membership for the same user must     fail]] - rationale - backend/tests/test_households.py
- [[Given raw rows from SQL, builds category breakdown with member totals and percen]] - rationale - backend/tests/test_household_settlement.py
- [[Invariant each user has AT MOST one active household_members row.     Enforced]] - rationale - backend/tests/test_households.py
- [[Invariant every users row has at least one active household_members row.     No]] - rationale - backend/tests/test_households.py
- [[Migration 034 must have created the partial unique index that prevents     a use]] - rationale - backend/tests/test_households.py
- [[No members — no transfers.]] - rationale - backend/tests/test_household_settlement.py
- [[Raise 403 if user is not a member of the household.]] - rationale - backend/modules/households/auth.py
- [[Returns empty list when no rows.]] - rationale - backend/tests/test_household_settlement.py
- [[Single member — no transfers needed.]] - rationale - backend/tests/test_household_settlement.py
- [[When both paid their fair share, no transfers.]] - rationale - backend/tests/test_household_settlement.py
- [[With 5050 split, person who paid less owes the difference.]] - rationale - backend/tests/test_household_settlement.py
- [[With 6040, settlement accounts for unequal expected shares.]] - rationale - backend/tests/test_household_settlement.py
- [[_equal_ratio()]] - code - backend/modules/households/service.py
- [[_round5()]] - code - backend/modules/budgets/allocation_service.py
- [[accept_invite()]] - code - backend/modules/households/service.py
- [[accept_invite()_1]] - code - backend/modules/households/router.py
- [[allocation_service.py]] - code - backend/modules/budgets/allocation_service.py
- [[auth.py]] - code - backend/modules/households/auth.py
- [[budget_v2()]] - code - backend/modules/budgets/router.py
- [[build_category_breakdown()]] - code - backend/modules/households/service.py
- [[calculate_settlement()]] - code - backend/modules/households/service.py
- [[category_breakdown()]] - code - backend/modules/households/router.py
- [[category_service.py]] - code - backend/modules/budgets/category_service.py
- [[compute_historical_suggestion()]] - code - backend/modules/budgets/allocation_service.py
- [[create_and_invite()]] - code - backend/modules/households/router.py
- [[create_bank_account()]] - code - backend/modules/bank_accounts/router.py
- [[create_household()_1]] - code - backend/modules/households/router.py
- [[create_invite()]] - code - backend/modules/households/service.py
- [[delete_bank_account()]] - code - backend/modules/bank_accounts/router.py
- [[get_allocation()]] - code - backend/modules/budgets/allocation_service.py
- [[get_budget_allocation()]] - code - backend/modules/budgets/router.py
- [[get_budget_status()]] - code - backend/modules/budgets/service.py
- [[get_cat_budgets()]] - code - backend/modules/budgets/router.py
- [[get_category_breakdown()]] - code - backend/modules/households/service.py
- [[get_category_budgets()]] - code - backend/modules/budgets/category_service.py
- [[get_contribution_summary()]] - code - backend/modules/households/service.py
- [[get_household_members()]] - code - backend/modules/households/service.py
- [[get_member_stats()]] - code - backend/modules/households/service.py
- [[get_members()]] - code - backend/modules/households/router.py
- [[get_pending_invites()]] - code - backend/modules/households/service.py
- [[get_settlement()]] - code - backend/modules/households/service.py
- [[get_split_ratio()]] - code - backend/modules/households/router.py
- [[household_summary()]] - code - backend/modules/households/router.py
- [[invite_member()]] - code - backend/modules/households/router.py
- [[list_bank_accounts()]] - code - backend/modules/bank_accounts/router.py
- [[member_stats()]] - code - backend/modules/households/router.py
- [[monthly_budget()]] - code - backend/modules/budgets/router.py
- [[personal_budget()]] - code - backend/modules/budgets/router.py
- [[remove_member()]] - code - backend/modules/households/service.py
- [[remove_member_endpoint()]] - code - backend/modules/households/router.py
- [[require_membership()]] - code - backend/modules/households/auth.py
- [[router.py_4]] - code - backend/modules/bank_accounts/router.py
- [[router.py_8]] - code - backend/modules/budgets/router.py
- [[router.py_9]] - code - backend/modules/households/router.py
- [[service.py_7]] - code - backend/modules/budgets/service.py
- [[service.py_8]] - code - backend/modules/households/service.py
- [[set_budget()]] - code - backend/modules/budgets/router.py
- [[set_budget_allocation()]] - code - backend/modules/budgets/router.py
- [[set_cat_budgets()]] - code - backend/modules/budgets/router.py
- [[set_category_budgets()]] - code - backend/modules/budgets/category_service.py
- [[set_monthly_budget()]] - code - backend/modules/budgets/service.py
- [[settlement()]] - code - backend/modules/households/router.py
- [[test_accept_invite_adds_member()]] - code - backend/tests/test_households.py
- [[test_budget_allocation_service.py]] - code - backend/tests/test_budget_allocation_service.py
- [[test_build_category_breakdown_empty()]] - code - backend/tests/test_household_settlement.py
- [[test_build_category_breakdown_groups_by_category()]] - code - backend/tests/test_household_settlement.py
- [[test_contribution_summary_returns_both_users()]] - code - backend/tests/test_household_privacy.py
- [[test_create_individual_household()]] - code - backend/tests/test_households.py
- [[test_create_invite_generates_token()]] - code - backend/tests/test_households.py
- [[test_default_allocation_sums_to_100()]] - code - backend/tests/test_budget_allocation_service.py
- [[test_historical_suggestion_excludes_zero_income_months()]] - code - backend/tests/test_budget_allocation_service.py
- [[test_historical_suggestion_returns_none_when_no_income_data()]] - code - backend/tests/test_budget_allocation_service.py
- [[test_historical_suggestion_rounds_to_nearest_5()]] - code - backend/tests/test_budget_allocation_service.py
- [[test_household_privacy.py]] - code - backend/tests/test_household_privacy.py
- [[test_household_settlement.py]] - code - backend/tests/test_household_settlement.py
- [[test_households.py]] - code - backend/tests/test_households.py
- [[test_member_stats_returns_only_aggregates()]] - code - backend/tests/test_household_privacy.py
- [[test_no_orphaned_users()]] - code - backend/tests/test_households.py
- [[test_no_user_has_multiple_active_memberships()]] - code - backend/tests/test_households.py
- [[test_partial_unique_index_blocks_duplicate_active()]] - code - backend/tests/test_households.py
- [[test_partial_unique_index_exists()]] - code - backend/tests/test_households.py
- [[test_settlement_3_members_equal_split()]] - code - backend/tests/test_household_settlement.py
- [[test_settlement_4_members_custom_ratio()]] - code - backend/tests/test_household_settlement.py
- [[test_settlement_50_50()]] - code - backend/tests/test_household_settlement.py
- [[test_settlement_60_40()]] - code - backend/tests/test_household_settlement.py
- [[test_settlement_all_zero()]] - code - backend/tests/test_household_settlement.py
- [[test_settlement_balanced()]] - code - backend/tests/test_household_settlement.py
- [[test_settlement_empty_members()]] - code - backend/tests/test_household_settlement.py
- [[test_settlement_single_member()]] - code - backend/tests/test_household_settlement.py
- [[update_bank_account()]] - code - backend/modules/bank_accounts/router.py
- [[update_member_role()]] - code - backend/modules/households/router.py
- [[update_settlement_enabled()]] - code - backend/modules/households/router.py
- [[update_split_ratio()]] - code - backend/modules/households/router.py
- [[upsert_allocation()]] - code - backend/modules/budgets/allocation_service.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Auth_&_Allocation_Services
SORT file.name ASC
```

## Connections to other communities
- 35 edges to [[_COMMUNITY_DB, Accounts & Allocation]]
- 6 edges to [[_COMMUNITY_Pydantic Schemas]]
- 2 edges to [[_COMMUNITY_Backend Core & Infra]]
- 2 edges to [[_COMMUNITY_Transactions API]]
- 1 edge to [[_COMMUNITY_Personal Budget Service]]
- 1 edge to [[_COMMUNITY_Budgets (v2 v3)]]

## Top bridge nodes
- [[compute_historical_suggestion()]] - degree 8, connects to 2 communities
- [[create_bank_account()]] - degree 5, connects to 2 communities
- [[require_membership()]] - degree 24, connects to 1 community
- [[router.py_9]] - degree 19, connects to 1 community
- [[service.py_8]] - degree 13, connects to 1 community