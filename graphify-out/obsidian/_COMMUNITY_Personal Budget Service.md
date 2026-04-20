---
type: community
cohesion: 0.19
members: 17
---

# Personal Budget Service

**Cohesion:** 0.19 - loosely connected
**Members:** 17 nodes

## Members
- [[Single mode, no allocation ceiling = income.]] - rationale - backend/tests/test_budget_personal_service.py
- [[When allocation exists, ceiling = income  personal_pct  100.]] - rationale - backend/tests/test_budget_personal_service.py
- [[When no allocation, ceiling = income - user_deposited.]] - rationale - backend/tests/test_budget_personal_service.py
- [[build_personal_block()]] - code - backend/modules/budgets/personal_service.py
- [[compute_pace()]] - code - backend/modules/budgets/personal_service.py
- [[compute_personal_ceiling()]] - code - backend/modules/budgets/personal_service.py
- [[get_personal_budget()]] - code - backend/modules/budgets/personal_service.py
- [[personal_service.py]] - code - backend/modules/budgets/personal_service.py
- [[test_budget_personal_service.py]] - code - backend/tests/test_budget_personal_service.py
- [[test_compute_pace_over_budget()]] - code - backend/tests/test_budget_personal_service.py
- [[test_compute_pace_under_budget()]] - code - backend/tests/test_budget_personal_service.py
- [[test_compute_pace_zero_spendable_budget()]] - code - backend/tests/test_budget_personal_service.py
- [[test_personal_ceiling_clamped_when_negative()]] - code - backend/tests/test_budget_personal_service.py
- [[test_personal_ceiling_percent_used_null_when_zero()]] - code - backend/tests/test_budget_personal_service.py
- [[test_personal_ceiling_single_mode_uses_income_when_no_allocation()]] - code - backend/tests/test_budget_personal_service.py
- [[test_personal_ceiling_uses_allocation_when_set()]] - code - backend/tests/test_budget_personal_service.py
- [[test_personal_ceiling_uses_waterfall_when_no_allocation()]] - code - backend/tests/test_budget_personal_service.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Personal_Budget_Service
SORT file.name ASC
```

## Connections to other communities
- 2 edges to [[_COMMUNITY_Backend Core & Infra]]
- 1 edge to [[_COMMUNITY_DB, Accounts & Allocation]]
- 1 edge to [[_COMMUNITY_Auth & Allocation Services]]

## Top bridge nodes
- [[get_personal_budget()]] - degree 7, connects to 3 communities
- [[compute_pace()]] - degree 6, connects to 1 community