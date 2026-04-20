---
source_file: "backend/modules/budgets/v2_schemas.py"
type: "code"
community: "DB, Accounts & Allocation"
location: "L57"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# RunwayBlock

## Connections
- [[BaseModel]] - `inherits` [EXTRACTED]
- [[Budget v2 service layer — computes the full `budgetsv2{household_id}` respons]] - `uses` [INFERRED]
- [[Build the budgetsv2 response for the given scope.      Args         db async]] - `uses` [INFERRED]
- [[Build the 4-level Hogar Sankey.      Levels       0 income source nodes — call]] - `uses` [INFERRED]
- [[Build the Personal Sankey. Structurally identical to the Hogar builder     but s]] - `uses` [INFERRED]
- [[Current day-of-month clamped to the month if we're viewing a past month.]] - `uses` [INFERRED]
- [[Days from today until the user's next payday.      If `user_budget_settings.payd]] - `uses` [INFERRED]
- [[Distinct currencies across transactions for the scope. Sorted asc.]] - `uses` [INFERRED]
- [[First-fit routing primitive used by the Sankey builders.      Pays `target` out]] - `uses` [INFERRED]
- [[Pull expense transactions for the month in one query.]] - `uses` [INFERRED]
- [[Read the caller's savings target via `user_budget_settings_service`.      Return]] - `uses` [INFERRED]
- [[Return (first_day_dt, first_day_next_dt, days_in_month) as UTC datetimes.]] - `uses` [INFERRED]
- [[Return any per-category monthly caps from `category_budgets` for this month.]] - `uses` [INFERRED]
- [[Return per-category (mean, pstdev, n) over the 3 preceding months.      Savings-]] - `uses` [INFERRED]
- [[Return the first-of-month `offset` calendar months before `month`.]] - `uses` [INFERRED]
- [[Sum of SHARED known_bills for members in `reimbursement` mode.      These bills]] - `uses` [INFERRED]
- [[Sum savings targets across members whose contribution_mode ∈ {full, fixed}.]] - `uses` [INFERRED]
- [[Trailing 14-day average of non-savings expense spend for this scope.]] - `uses` [INFERRED]
- [[get_budget_v2()]] - `calls` [INFERRED]
- [[v2_schemas.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/DB,_Accounts_&_Allocation