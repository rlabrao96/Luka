---
source_file: "backend/modules/households/contribution_service.py"
type: "code"
community: "DB, Accounts & Allocation"
location: "L75"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# HouseholdIncomeBreakdown

## Connections
- [[.test_fixed_member_node_labeled_contribucion_fija()]] - `calls` [INFERRED]
- [[.test_has_expected_fields()]] - `calls` [INFERRED]
- [[Budget v2 service layer — computes the full `budgetsv2{household_id}` respons]] - `uses` [INFERRED]
- [[Budget v3 Sankey tests — multi-level structure, caller-relative privacy, flow co]] - `uses` [INFERRED]
- [[Build the budgetsv2 response for the given scope.      Args         db async]] - `uses` [INFERRED]
- [[Build the 4-level Hogar Sankey.      Levels       0 income source nodes — call]] - `uses` [INFERRED]
- [[Build the Personal Sankey. Structurally identical to the Hogar builder     but s]] - `uses` [INFERRED]
- [[Caller's income transactions whose category appears in their         user_catego]] - `uses` [INFERRED]
- [[Current day-of-month clamped to the month if we're viewing a past month.]] - `uses` [INFERRED]
- [[Days from today until the user's next payday.      If `user_budget_settings.payd]] - `uses` [INFERRED]
- [[Distinct currencies across transactions for the scope. Sorted asc.]] - `uses` [INFERRED]
- [[End-to-end caller-relative tests against the live seeded DB.]] - `uses` [INFERRED]
- [[Every non-source  non-terminal node inflow == outflow == value.]] - `uses` [INFERRED]
- [[Every seeded household + currency + view Sankey flow must be         conservati]] - `uses` [INFERRED]
- [[First-fit routing primitive used by the Sankey builders.      Pays `target` out]] - `uses` [INFERRED]
- [[Flow conservation across all seeded households + view combinations.]] - `uses` [INFERRED]
- [[Full+full household with synthetic income rafa-full's household         view sh]] - `uses` [INFERRED]
- [[HOGAR FIXED with synthetic income seeded for both members.      rafa-fixed is in]] - `uses` [INFERRED]
- [[HOGAR REIMB rafa is `full`, partner is `reimbursement`.      Even though partne]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[Insert a synthetic income transaction inside the wrapping SAVEPOINT.]] - `uses` [INFERRED]
- [[Mixed full+fixed household in household view the fixed member         (partner-]] - `uses` [INFERRED]
- [[Personal view has meta_ahorro_personal  gastos_fijos_personal          disponi]] - `uses` [INFERRED]
- [[Personal view must never emit member_ aggregate nodes — those are         househ]] - `uses` [INFERRED]
- [[Privacy regression fixed-mode member's real income must NEVER appear         in]] - `uses` [INFERRED]
- [[Pull expense transactions for the month in one query.]] - `uses` [INFERRED]
- [[Quick sanity check on the shared helper — the real regression is above.]] - `uses` [INFERRED]
- [[Read the caller's savings target via `user_budget_settings_service`.      Return]] - `uses` [INFERRED]
- [[Regression tests for the contribution_service module (Chunk D).  These exercise]] - `uses` [INFERRED]
- [[Return (first_day_dt, first_day_next_dt, days_in_month) as UTC datetimes.]] - `uses` [INFERRED]
- [[Return True if forbidden appears as a numeric leaf (float comparison).]] - `uses` [INFERRED]
- [[Return any per-category monthly caps from `category_budgets` for this month.]] - `uses` [INFERRED]
- [[Return node-level flow conservation violations (tolerance ±1 for rounding).]] - `uses` [INFERRED]
- [[Return per-category (mean, pstdev, n) over the 3 preceding months.      Savings-]] - `uses` [INFERRED]
- [[Return the first-of-month `offset` calendar months before `month`.]] - `uses` [INFERRED]
- [[Smoke test against the rafa-full seeded household. The new         breakdown fun]] - `uses` [INFERRED]
- [[Sum of SHARED known_bills for members in `reimbursement` mode.      These bills]] - `uses` [INFERRED]
- [[Sum savings targets across members whose contribution_mode ∈ {full, fixed}.]] - `uses` [INFERRED]
- [[TestBuildHogarSankey]] - `uses` [INFERRED]
- [[TestBuildPersonalSankey]] - `uses` [INFERRED]
- [[TestCallerRelativeEndToEnd]] - `uses` [INFERRED]
- [[TestFlowConservationAllSeeds]] - `uses` [INFERRED]
- [[TestHouseholdIncomeBreakdownDataclass]] - `uses` [INFERRED]
- [[TestIncomeBreakdownForHouseholdView]] - `uses` [INFERRED]
- [[TestPayFirstFit]] - `uses` [INFERRED]
- [[TestSankeyNodeAdditiveFields]] - `uses` [INFERRED]
- [[The caller must never appear in their own other_members list.]] - `uses` [INFERRED]
- [[Trailing 14-day average of non-savings expense spend for this scope.]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[Yield every leaf value in a nested dictlist structure.]] - `uses` [INFERRED]
- [[_sample_breakdown_full_full()]] - `calls` [INFERRED]
- [[contribution_service.py]] - `contains` [EXTRACTED]
- [[income_breakdown_for_household_view()]] - `calls` [EXTRACTED]
- [[partner-fixed in personal view sees their REAL income (not fixed amount).      P]] - `uses` [INFERRED]
- [[rafa-fixed (full mode) in personal view returns their real income.]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/DB,_Accounts_&_Allocation