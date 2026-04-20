---
type: community
cohesion: 0.18
members: 29
---

# Household Contributions

**Cohesion:** 0.18 - loosely connected
**Members:** 29 nodes

## Members
- [[Raise AssertionError if any leaf equals ``forbidden_value``.      Decimal-aware]] - rationale - backend/tests/helpers/json_walk.py
- [[Shared JSON-walking helpers for privacy  redaction tests.  Chunk C wrote a loca]] - rationale - backend/tests/helpers/json_walk.py
- [[Yield every leaf value in a JSON-parsed structure.      Descends into dicts (val]] - rationale - backend/tests/helpers/json_walk.py
- [[_current_month()]] - code - backend/tests/test_contribution_modes.py
- [[_get_seed_household_id()]] - code - backend/tests/test_contribution_modes.py
- [[_get_seed_user()]] - code - backend/tests/test_contribution_modes.py
- [[_household_by_name()]] - code - backend/tests/test_contribution_modes.py
- [[_insert_income()]] - code - backend/tests/test_contribution_modes.py
- [[_month_bounds_datetime()_1]] - code - backend/modules/households/contribution_service.py
- [[_user_by_email()]] - code - backend/tests/test_contribution_modes.py
- [[assert_value_absent()]] - code - backend/tests/helpers/json_walk.py
- [[contribution_service.py]] - code - backend/modules/households/contribution_service.py
- [[income_breakdown_for_household_view()]] - code - backend/modules/households/contribution_service.py
- [[income_for_household_view()]] - code - backend/modules/households/contribution_service.py
- [[income_for_personal_view()]] - code - backend/modules/households/contribution_service.py
- [[json_walk.py]] - code - backend/tests/helpers/json_walk.py
- [[test_breakdown_never_reads_fixed_member_real_income()]] - code - backend/tests/test_contribution_modes.py
- [[test_caller_relative_for_seed_user()]] - code - backend/tests/test_contribution_modes.py
- [[test_caller_sources_keys_match_user_categories()]] - code - backend/tests/test_contribution_modes.py
- [[test_contribution_modes.py]] - code - backend/tests/test_contribution_modes.py
- [[test_household_view_reimbursement_mode_contributes_zero()]] - code - backend/tests/test_contribution_modes.py
- [[test_household_view_sums_full_real_plus_fixed_amount()]] - code - backend/tests/test_contribution_modes.py
- [[test_other_members_excludes_caller_themselves()]] - code - backend/tests/test_contribution_modes.py
- [[test_personal_view_fixed_member_sees_own_real_income()]] - code - backend/tests/test_contribution_modes.py
- [[test_personal_view_full_member_sees_own_real_income()]] - code - backend/tests/test_contribution_modes.py
- [[test_total_equals_components_sum()]] - code - backend/tests/test_contribution_modes.py
- [[test_walk_json_helper_finds_forbidden_value()]] - code - backend/tests/test_contribution_modes.py
- [[update_contribution()]] - code - backend/modules/households/contribution_service.py
- [[walk_json()]] - code - backend/tests/helpers/json_walk.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Household_Contributions
SORT file.name ASC
```

## Connections to other communities
- 20 edges to [[_COMMUNITY_DB, Accounts & Allocation]]
- 1 edge to [[_COMMUNITY_Budgets (v2 v3)]]
- 1 edge to [[_COMMUNITY_Pydantic Schemas]]

## Top bridge nodes
- [[income_breakdown_for_household_view()]] - degree 12, connects to 2 communities
- [[update_contribution()]] - degree 3, connects to 2 communities
- [[test_contribution_modes.py]] - degree 19, connects to 1 community
- [[_insert_income()]] - degree 9, connects to 1 community
- [[contribution_service.py]] - degree 8, connects to 1 community