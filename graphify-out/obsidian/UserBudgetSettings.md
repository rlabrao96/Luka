---
source_file: "backend/modules/budgets/user_budget_settings_models.py"
type: "code"
community: "DB, Accounts & Allocation"
location: "L10"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# UserBudgetSettings

## Connections
- [[Base]] - `uses` [INFERRED]
- [[Base_1]] - `inherits` [EXTRACTED]
- [[Deep-overspent case seeded HOGAR FULL has no income transactions     but subscr]] - `uses` [INFERRED]
- [[Even when income is positive but `known_bills + cuotas + savings_target`     tog]] - `uses` [INFERRED]
- [[Fetch the user's settings row, creating it with null defaults if missing.]] - `uses` [INFERRED]
- [[Household aggregate = sum across members whose contribution_mode         is 'ful]] - `uses` [INFERRED]
- [[Integration tests for the `budgetsv2{household_id}` endpoint.  These hit the]] - `uses` [INFERRED]
- [[Prevents drift between the committed contract fixture and the live schema.]] - `uses` [INFERRED]
- [[Privacy invariant even when we SEED partner real income, household view     mus]] - `uses` [INFERRED]
- [[Read the user's personal_allocation_amount in the requested currency.      Retur]] - `uses` [INFERRED]
- [[Recursively assert `forbidden` never appears as a numeric leaf value.]] - `uses` [INFERRED]
- [[Return a list of node ids where inflowoutflow don't match the node.      Interm]] - `uses` [INFERRED]
- [[Return the user's payday day-of-month, or None if unset.]] - `uses` [INFERRED]
- [[Return the user's savings target in the requested currency, or 0 if mismatch.]] - `uses` [INFERRED]
- [[Service for user_budget_settings (savings target + payday).  Chunk C wrote inlin]] - `uses` [INFERRED]
- [[Set (or clear with ``amount=None``) the user's monthly personal spending allocat]] - `uses` [INFERRED]
- [[Set (or clear with `day=None`) the caller's payday day-of-month.      Raises Val]] - `uses` [INFERRED]
- [[Set a user_budget_settings row and verify the service echoes it back.]] - `uses` [INFERRED]
- [[Set the caller's monthly savings target and its currency.      Passing `amount=N]] - `uses` [INFERRED]
- [[Sum personal_allocation_amount across members whose contribution_mode     is 'fu]] - `uses` [INFERRED]
- [[Sum savings targets across active household members in the given currency.]] - `uses` [INFERRED]
- [[TestPersonalAllocation]] - `uses` [INFERRED]
- [[Transactions in savings-equivalent categories (e.g. 'Inversión')     must NOT co]] - `uses` [INFERRED]
- [[Write path setting persists, clearing with amount=None removes.]] - `uses` [INFERRED]
- [[Yield every leaf value in a nested dictlist structure._1]] - `uses` [INFERRED]
- [[get_or_create()]] - `calls` [INFERRED]
- [[household view income = sum(fullreal, fixedfixed_amount, reimb0).      Seed r]] - `uses` [INFERRED]
- [[household view on HOGAR FULL returns a valid response.]] - `uses` [INFERRED]
- [[rafa-fixed has both CLP and USD txns — both must surface in the picker.]] - `uses` [INFERRED]
- [[rafa-full in personal view returns a valid response and a live cuota block.]] - `uses` [INFERRED]
- [[test_sankey_flow_conservation_fixed_outflow_exceeds_income()]] - `calls` [INFERRED]
- [[test_savings_target_reads_from_user_budget_settings()]] - `calls` [INFERRED]
- [[user_budget_settings_models.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/DB,_Accounts_&_Allocation