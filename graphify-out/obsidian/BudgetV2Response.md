---
source_file: "backend/modules/budgets/v2_schemas.py"
type: "code"
community: "DB, Accounts & Allocation"
location: "L76"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# BudgetV2Response

## Connections
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[Budget v2 service layer — computes the full `budgetsv2{household_id}` respons]] - `uses` [INFERRED]
- [[Build the budgetsv2 response for the given scope.      Args         db async]] - `uses` [INFERRED]
- [[Build the 4-level Hogar Sankey.      Levels       0 income source nodes — call]] - `uses` [INFERRED]
- [[Build the Personal Sankey. Structurally identical to the Hogar builder     but s]] - `uses` [INFERRED]
- [[Current day-of-month clamped to the month if we're viewing a past month.]] - `uses` [INFERRED]
- [[Days from today until the user's next payday.      If `user_budget_settings.payd]] - `uses` [INFERRED]
- [[Deep-overspent case seeded HOGAR FULL has no income transactions     but subscr]] - `uses` [INFERRED]
- [[Distinct currencies across transactions for the scope. Sorted asc.]] - `uses` [INFERRED]
- [[Even when income is positive but `known_bills + cuotas + savings_target`     tog]] - `uses` [INFERRED]
- [[First-fit routing primitive used by the Sankey builders.      Pays `target` out]] - `uses` [INFERRED]
- [[Integration tests for the `budgetsv2{household_id}` endpoint.  These hit the]] - `uses` [INFERRED]
- [[Prevents drift between the committed contract fixture and the live schema.]] - `uses` [INFERRED]
- [[Privacy invariant even when we SEED partner real income, household view     mus]] - `uses` [INFERRED]
- [[Pull expense transactions for the month in one query.]] - `uses` [INFERRED]
- [[Read the caller's savings target via `user_budget_settings_service`.      Return]] - `uses` [INFERRED]
- [[Recursively assert `forbidden` never appears as a numeric leaf value.]] - `uses` [INFERRED]
- [[Return (first_day_dt, first_day_next_dt, days_in_month) as UTC datetimes.]] - `uses` [INFERRED]
- [[Return a list of node ids where inflowoutflow don't match the node.      Interm]] - `uses` [INFERRED]
- [[Return any per-category monthly caps from `category_budgets` for this month.]] - `uses` [INFERRED]
- [[Return per-category (mean, pstdev, n) over the 3 preceding months.      Savings-]] - `uses` [INFERRED]
- [[Return the first-of-month `offset` calendar months before `month`.]] - `uses` [INFERRED]
- [[Set a user_budget_settings row and verify the service echoes it back.]] - `uses` [INFERRED]
- [[Sum of SHARED known_bills for members in `reimbursement` mode.      These bills]] - `uses` [INFERRED]
- [[Sum savings targets across members whose contribution_mode ∈ {full, fixed}.]] - `uses` [INFERRED]
- [[Trailing 14-day average of non-savings expense spend for this scope.]] - `uses` [INFERRED]
- [[Transactions in savings-equivalent categories (e.g. 'Inversión')     must NOT co]] - `uses` [INFERRED]
- [[Yield every leaf value in a nested dictlist structure._1]] - `uses` [INFERRED]
- [[get_budget_v2()]] - `calls` [INFERRED]
- [[household view income = sum(fullreal, fixedfixed_amount, reimb0).      Seed r]] - `uses` [INFERRED]
- [[household view on HOGAR FULL returns a valid response.]] - `uses` [INFERRED]
- [[rafa-fixed has both CLP and USD txns — both must surface in the picker.]] - `uses` [INFERRED]
- [[rafa-full in personal view returns a valid response and a live cuota block.]] - `uses` [INFERRED]
- [[v2_schemas.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/DB,_Accounts_&_Allocation