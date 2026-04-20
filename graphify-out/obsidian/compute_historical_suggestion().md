---
source_file: "backend/modules/budgets/allocation_service.py"
type: "code"
community: "Auth & Allocation Services"
location: "L18"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Auth_&_Allocation_Services
---

# compute_historical_suggestion()

## Connections
- [[GET()]] - `calls` [INFERRED]
- [[Given a list of {income, hogar_spent, personal_spent} dicts,     compute the ave]] - `rationale_for` [EXTRACTED]
- [[_round5()]] - `calls` [EXTRACTED]
- [[allocation_service.py]] - `contains` [EXTRACTED]
- [[get_allocation()]] - `calls` [EXTRACTED]
- [[test_historical_suggestion_excludes_zero_income_months()]] - `calls` [INFERRED]
- [[test_historical_suggestion_returns_none_when_no_income_data()]] - `calls` [INFERRED]
- [[test_historical_suggestion_rounds_to_nearest_5()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Auth_&_Allocation_Services