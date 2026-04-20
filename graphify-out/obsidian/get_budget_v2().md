---
source_file: "backend/modules/budgets/v2_service.py"
type: "code"
community: "Budgets (v2 v3)"
location: "L862"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Budgets_(v2_v3)
---

# get_budget_v2()

## Connections
- [[BudgetV2Response]] - `calls` [INFERRED]
- [[Build the budgetsv2 response for the given scope.      Args         db async]] - `rationale_for` [EXTRACTED]
- [[CuotasBlock]] - `calls` [INFERRED]
- [[GET()]] - `calls` [INFERRED]
- [[RiskCategory]] - `calls` [INFERRED]
- [[RunwayBlock]] - `calls` [INFERRED]
- [[SavingsTargetBlock]] - `calls` [INFERRED]
- [[SpendableBlock]] - `calls` [INFERRED]
- [[_build_hogar_sankey()]] - `calls` [EXTRACTED]
- [[_build_personal_sankey()]] - `calls` [EXTRACTED]
- [[_category_caps()]] - `calls` [EXTRACTED]
- [[_currencies_available()]] - `calls` [EXTRACTED]
- [[_daily_burn_14d()]] - `calls` [EXTRACTED]
- [[_days_to_payday()]] - `calls` [EXTRACTED]
- [[_fetch_month_transactions()]] - `calls` [EXTRACTED]
- [[_household_savings_target()]] - `calls` [EXTRACTED]
- [[_month_bounds_datetime()]] - `calls` [EXTRACTED]
- [[_personal_savings_target()]] - `calls` [EXTRACTED]
- [[_reimbursement_members_known_bills()]] - `calls` [EXTRACTED]
- [[_three_month_category_stats()]] - `calls` [EXTRACTED]
- [[_today_day_in_month()]] - `calls` [EXTRACTED]
- [[budget_v2()]] - `calls` [INFERRED]
- [[get_active_cuotas_summary()]] - `calls` [INFERRED]
- [[get_household_known_bills()]] - `calls` [INFERRED]
- [[get_household_personal_allocation()]] - `calls` [INFERRED]
- [[get_user_known_bills()]] - `calls` [INFERRED]
- [[income_breakdown_for_household_view()]] - `calls` [INFERRED]
- [[is_savings_category()]] - `calls` [INFERRED]
- [[overshoot_probability()]] - `calls` [INFERRED]
- [[pace_forecast()]] - `calls` [INFERRED]
- [[runway_days()]] - `calls` [INFERRED]
- [[select_risk_categories()]] - `calls` [INFERRED]
- [[spendable_ceiling()]] - `calls` [INFERRED]
- [[test_caller_sees_own_sources_and_partner_as_aggregate()]] - `calls` [INFERRED]
- [[test_fixed_member_node_value_equals_contribution_amount()]] - `calls` [INFERRED]
- [[test_flow_conservation()]] - `calls` [INFERRED]
- [[test_hogar_fixed_currencies_available()]] - `calls` [INFERRED]
- [[test_hogar_fixed_household_income_respects_fixed_contribution()]] - `calls` [INFERRED]
- [[test_hogar_fixed_privacy_partner_amount_synthetic()]] - `calls` [INFERRED]
- [[test_hogar_full_household_view_smoke()]] - `calls` [INFERRED]
- [[test_hogar_full_personal_view_smoke()]] - `calls` [INFERRED]
- [[test_investment_category_excluded_from_spendable_spent()]] - `calls` [INFERRED]
- [[test_personal_view_has_no_member_nodes()]] - `calls` [INFERRED]
- [[test_sankey_flow_conservation_fixed_outflow_exceeds_income()]] - `calls` [INFERRED]
- [[test_sankey_flow_conservation_overspent_hogar_full()]] - `calls` [INFERRED]
- [[test_savings_target_reads_from_user_budget_settings()]] - `calls` [INFERRED]
- [[v2_service.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Budgets_(v2_v3)