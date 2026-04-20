---
source_file: "backend/tests/test_budget_v3_sankey.py"
type: "code"
community: "Budgets (v2 v3)"
location: "L61"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Budgets_(v2_v3)
---

# TestPayFirstFit

## Connections
- [[.test_enough_income_covers_target()]] - `method` [EXTRACTED]
- [[.test_partial_income_splits_between_income_and_otras()]] - `method` [EXTRACTED]
- [[.test_zero_income_sends_full_target_to_otras()]] - `method` [EXTRACTED]
- [[.test_zero_target_returns_zero_zero()]] - `method` [EXTRACTED]
- [[Household]] - `uses` [INFERRED]
- [[HouseholdIncomeBreakdown]] - `uses` [INFERRED]
- [[OtherMemberContribution]] - `uses` [INFERRED]
- [[SankeyNode]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[test_budget_v3_sankey.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Budgets_(v2_v3)