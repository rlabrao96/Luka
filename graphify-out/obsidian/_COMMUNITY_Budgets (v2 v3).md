---
type: community
cohesion: 0.04
members: 109
---

# Budgets (v2 v3)

**Cohesion:** 0.04 - loosely connected
**Members:** 109 nodes

## Members
- [[.test_emits_level_0_sources_for_caller()]] - code - backend/tests/test_budget_v3_sankey.py
- [[.test_enough_income_covers_target()]] - code - backend/tests/test_budget_v3_sankey.py
- [[.test_fixed_member_node_labeled_contribucion_fija()]] - code - backend/tests/test_budget_v3_sankey.py
- [[.test_flow_conservation()]] - code - backend/tests/test_budget_v3_sankey.py
- [[.test_flow_conservation_each_intermediate()]] - code - backend/tests/test_budget_v3_sankey.py
- [[.test_gasto_personal_hidden_when_zero()]] - code - backend/tests/test_budget_v3_sankey.py
- [[.test_ingresos_hogar_is_level_1_hub()]] - code - backend/tests/test_budget_v3_sankey.py
- [[.test_level_0_is_caller_sources_only_no_other_members()]] - code - backend/tests/test_budget_v3_sankey.py
- [[.test_level_0_nodes_have_level_zero_and_kind_source()]] - code - backend/tests/test_budget_v3_sankey.py
- [[.test_level_1_hub_exists()]] - code - backend/tests/test_budget_v3_sankey.py
- [[.test_level_2_allocation_nodes_are_level_two()]] - code - backend/tests/test_budget_v3_sankey.py
- [[.test_level_2_has_three_allocation_nodes_no_gasto_personal()]] - code - backend/tests/test_budget_v3_sankey.py
- [[.test_partial_income_splits_between_income_and_otras()]] - code - backend/tests/test_budget_v3_sankey.py
- [[.test_personal_allocation_default_is_zero()]] - code - backend/tests/test_budget_forecast.py
- [[.test_personal_allocation_overspent_clamps_to_zero()]] - code - backend/tests/test_budget_forecast.py
- [[.test_personal_allocation_subtracts_from_spendable()]] - code - backend/tests/test_budget_forecast.py
- [[.test_zero_income_sends_full_target_to_otras()]] - code - backend/tests/test_budget_v3_sankey.py
- [[.test_zero_target_returns_zero_zero()]] - code - backend/tests/test_budget_v3_sankey.py
- [[Day 1 should be treated as day 3 so a single-day total doesn't explode.]] - rationale - backend/tests/test_budget_forecast.py
- [[Discretionary budget = income minus fixed commitments.      Clamped to 0 — a neg]] - rationale - backend/modules/budgets/forecast.py
- [[Gaussian P(actual  cap) given `projected` as the mean and `std` as σ.      Uses]] - rationale - backend/modules/budgets/forecast.py
- [[Heuristic v1 forecast engine for budget-v2.  These are intentionally simple func]] - rationale - backend/modules/budgets/forecast.py
- [[How many days of runway given remaining budget and the 14-day burn rate.      Ze]] - rationale - backend/modules/budgets/forecast.py
- [[Linearly project final spend from MTD, guarding early-month noise.      Returns]] - rationale - backend/modules/budgets/forecast.py
- [[Omitting the kwarg preserves back-compat with v2 callers.]] - rationale - backend/tests/test_budget_forecast.py
- [[Rank categories by `share × CV`, return top N as `(name, score)`.      Intuiti]] - rationale - backend/modules/budgets/forecast.py
- [[Return (mean, population stdev, n) over a list of monthly totals.      Empty ite]] - rationale - backend/modules/budgets/forecast.py
- [[Single source of truth for which transaction categories are 'savings-equivalent']] - rationale - backend/modules/budgets/savings_categories.py
- [[TestBuildHogarSankey]] - code - backend/tests/test_budget_v3_sankey.py
- [[TestBuildPersonalSankey]] - code - backend/tests/test_budget_v3_sankey.py
- [[TestPayFirstFit]] - code - backend/tests/test_budget_v3_sankey.py
- [[TestSpendableCeilingPersonalAllocation]] - code - backend/tests/test_budget_forecast.py
- [[Unit tests for the v1 heuristic forecast engine.  These tests lock in the math f]] - rationale - backend/tests/test_budget_forecast.py
- [[_assert_value_absent()]] - code - backend/tests/test_budget_v2_endpoint.py
- [[_build_hogar_sankey()]] - code - backend/modules/budgets/v2_service.py
- [[_build_personal_sankey()]] - code - backend/modules/budgets/v2_service.py
- [[_category_caps()]] - code - backend/modules/budgets/v2_service.py
- [[_currencies_available()]] - code - backend/modules/budgets/v2_service.py
- [[_current_month()_1]] - code - backend/tests/test_budget_v3_sankey.py
- [[_current_month()_2]] - code - backend/tests/test_budget_v2_endpoint.py
- [[_daily_burn_14d()]] - code - backend/modules/budgets/v2_service.py
- [[_days_to_payday()]] - code - backend/modules/budgets/v2_service.py
- [[_fetch_month_transactions()]] - code - backend/modules/budgets/v2_service.py
- [[_flow_conservation_errors()]] - code - backend/tests/test_budget_v3_sankey.py
- [[_flow_conservation_errors()_1]] - code - backend/tests/test_budget_v2_endpoint.py
- [[_household_by_name()_1]] - code - backend/tests/test_budget_v3_sankey.py
- [[_household_by_name()_2]] - code - backend/tests/test_budget_v2_endpoint.py
- [[_month_bounds_date()]] - code - backend/modules/budgets/v2_service.py
- [[_month_bounds_datetime()]] - code - backend/modules/budgets/v2_service.py
- [[_normalize()]] - code - backend/modules/budgets/savings_categories.py
- [[_pay_first_fit()]] - code - backend/modules/budgets/v2_service.py
- [[_prior_month()]] - code - backend/modules/budgets/v2_service.py
- [[_reimbursement_members_known_bills()]] - code - backend/modules/budgets/v2_service.py
- [[_sample_breakdown_full_full()]] - code - backend/tests/test_budget_v3_sankey.py
- [[_slugify()]] - code - backend/modules/budgets/v2_service.py
- [[_three_month_category_stats()]] - code - backend/modules/budgets/v2_service.py
- [[_today_day_in_month()]] - code - backend/modules/budgets/v2_service.py
- [[_user_by_email()_1]] - code - backend/tests/test_budget_v3_sankey.py
- [[_user_by_email()_2]] - code - backend/tests/test_budget_v2_endpoint.py
- [[_value_present_in_json()]] - code - backend/tests/test_budget_v3_sankey.py
- [[_walk_json()]] - code - backend/tests/test_budget_v2_endpoint.py
- [[_walk_json_values()]] - code - backend/tests/test_budget_v3_sankey.py
- [[category_stats()]] - code - backend/modules/budgets/forecast.py
- [[forecast.py]] - code - backend/modules/budgets/forecast.py
- [[get_budget_v2()]] - code - backend/modules/budgets/v2_service.py
- [[is_savings_category()]] - code - backend/modules/budgets/savings_categories.py
- [[overshoot_probability()]] - code - backend/modules/budgets/forecast.py
- [[pace_forecast()]] - code - backend/modules/budgets/forecast.py
- [[runway_days()]] - code - backend/modules/budgets/forecast.py
- [[savings_categories.py]] - code - backend/modules/budgets/savings_categories.py
- [[select_risk_categories()]] - code - backend/modules/budgets/forecast.py
- [[spendable_ceiling()]] - code - backend/modules/budgets/forecast.py
- [[test_budget_forecast.py]] - code - backend/tests/test_budget_forecast.py
- [[test_budget_v2_endpoint.py]] - code - backend/tests/test_budget_v2_endpoint.py
- [[test_budget_v3_sankey.py]] - code - backend/tests/test_budget_v3_sankey.py
- [[test_caller_sees_own_sources_and_partner_as_aggregate()]] - code - backend/tests/test_budget_v3_sankey.py
- [[test_category_stats_empty()]] - code - backend/tests/test_budget_forecast.py
- [[test_category_stats_single_value()]] - code - backend/tests/test_budget_forecast.py
- [[test_category_stats_three_value_series()]] - code - backend/tests/test_budget_forecast.py
- [[test_contract_fixture_matches_pydantic_schema()]] - code - backend/tests/test_budget_v2_endpoint.py
- [[test_fixed_member_node_value_equals_contribution_amount()]] - code - backend/tests/test_budget_v3_sankey.py
- [[test_flow_conservation()]] - code - backend/tests/test_budget_v3_sankey.py
- [[test_hogar_fixed_currencies_available()]] - code - backend/tests/test_budget_v2_endpoint.py
- [[test_hogar_fixed_household_income_respects_fixed_contribution()]] - code - backend/tests/test_budget_v2_endpoint.py
- [[test_hogar_fixed_privacy_partner_amount_synthetic()]] - code - backend/tests/test_budget_v2_endpoint.py
- [[test_hogar_full_household_view_smoke()]] - code - backend/tests/test_budget_v2_endpoint.py
- [[test_hogar_full_personal_view_smoke()]] - code - backend/tests/test_budget_v2_endpoint.py
- [[test_investment_category_excluded_from_spendable_spent()]] - code - backend/tests/test_budget_v2_endpoint.py
- [[test_overshoot_probability_at_cap()]] - code - backend/tests/test_budget_forecast.py
- [[test_overshoot_probability_high()]] - code - backend/tests/test_budget_forecast.py
- [[test_overshoot_probability_low()]] - code - backend/tests/test_budget_forecast.py
- [[test_overshoot_probability_zero_std_hard_threshold()]] - code - backend/tests/test_budget_forecast.py
- [[test_pace_forecast_day_three_guard()]] - code - backend/tests/test_budget_forecast.py
- [[test_pace_forecast_end_of_month()]] - code - backend/tests/test_budget_forecast.py
- [[test_pace_forecast_midmonth_no_guard()]] - code - backend/tests/test_budget_forecast.py
- [[test_personal_view_has_no_member_nodes()]] - code - backend/tests/test_budget_v3_sankey.py
- [[test_runway_days_basic()]] - code - backend/tests/test_budget_forecast.py
- [[test_runway_days_zero_burn()]] - code - backend/tests/test_budget_forecast.py
- [[test_runway_days_zero_remaining()]] - code - backend/tests/test_budget_forecast.py
- [[test_sankey_flow_conservation_fixed_outflow_exceeds_income()]] - code - backend/tests/test_budget_v2_endpoint.py
- [[test_sankey_flow_conservation_overspent_hogar_full()]] - code - backend/tests/test_budget_v2_endpoint.py
- [[test_savings_target_reads_from_user_budget_settings()]] - code - backend/tests/test_budget_v2_endpoint.py
- [[test_select_risk_categories_ranks_by_share_times_cv()]] - code - backend/tests/test_budget_forecast.py
- [[test_select_risk_categories_skips_zero_mean()]] - code - backend/tests/test_budget_forecast.py
- [[test_select_risk_categories_top_n_limits_output()]] - code - backend/tests/test_budget_forecast.py
- [[test_spendable_ceiling_basic()]] - code - backend/tests/test_budget_forecast.py
- [[test_spendable_ceiling_clamped_to_zero()]] - code - backend/tests/test_budget_forecast.py
- [[test_spendable_ceiling_decimal_precision()]] - code - backend/tests/test_budget_forecast.py
- [[v2_service.py]] - code - backend/modules/budgets/v2_service.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Budgets_(v2_v3)
SORT file.name ASC
```

## Connections to other communities
- 76 edges to [[_COMMUNITY_DB, Accounts & Allocation]]
- 7 edges to [[_COMMUNITY_Backend Core & Infra]]
- 6 edges to [[_COMMUNITY_User Budget Settings]]
- 3 edges to [[_COMMUNITY_Plaid & Subscriptions]]
- 1 edge to [[_COMMUNITY_Cuotas (Installments)]]
- 1 edge to [[_COMMUNITY_Household Contributions]]
- 1 edge to [[_COMMUNITY_Auth & Allocation Services]]

## Top bridge nodes
- [[get_budget_v2()]] - degree 47, connects to 7 communities
- [[v2_service.py]] - degree 19, connects to 2 communities
- [[_build_hogar_sankey()]] - degree 15, connects to 2 communities
- [[_build_personal_sankey()]] - degree 12, connects to 2 communities
- [[.test_flow_conservation_each_intermediate()]] - degree 5, connects to 2 communities