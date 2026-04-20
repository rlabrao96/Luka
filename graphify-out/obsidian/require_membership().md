---
source_file: "backend/modules/households/auth.py"
type: "code"
community: "Auth & Allocation Services"
location: "L8"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Auth_&_Allocation_Services
---

# require_membership()

## Connections
- [[Raise 403 if user is not a member of the household.]] - `rationale_for` [EXTRACTED]
- [[auth.py]] - `contains` [EXTRACTED]
- [[budget_v2()]] - `calls` [INFERRED]
- [[category_breakdown()]] - `calls` [INFERRED]
- [[create_bank_account()]] - `calls` [INFERRED]
- [[delete_bank_account()]] - `calls` [INFERRED]
- [[get_budget_allocation()]] - `calls` [INFERRED]
- [[get_cat_budgets()]] - `calls` [INFERRED]
- [[get_members()]] - `calls` [INFERRED]
- [[get_split_ratio()]] - `calls` [INFERRED]
- [[household_summary()]] - `calls` [INFERRED]
- [[list_bank_accounts()]] - `calls` [INFERRED]
- [[member_stats()]] - `calls` [INFERRED]
- [[monthly_budget()]] - `calls` [INFERRED]
- [[monthly_summary()]] - `calls` [INFERRED]
- [[personal_budget()]] - `calls` [INFERRED]
- [[set_budget()]] - `calls` [INFERRED]
- [[set_budget_allocation()]] - `calls` [INFERRED]
- [[set_cat_budgets()]] - `calls` [INFERRED]
- [[settlement()]] - `calls` [INFERRED]
- [[shared_transactions()]] - `calls` [INFERRED]
- [[update_bank_account()]] - `calls` [INFERRED]
- [[update_settlement_enabled()]] - `calls` [INFERRED]
- [[update_split_ratio()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Auth_&_Allocation_Services