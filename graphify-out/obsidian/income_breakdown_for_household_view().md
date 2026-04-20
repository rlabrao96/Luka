---
source_file: "backend/modules/households/contribution_service.py"
type: "code"
community: "Household Contributions"
location: "L172"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Household_Contributions
---

# income_breakdown_for_household_view()

## Connections
- [[HouseholdIncomeBreakdown]] - `calls` [EXTRACTED]
- [[OtherMemberContribution]] - `calls` [EXTRACTED]
- [[Return a caller-relative breakdown of household income for the month.      PRIVA]] - `rationale_for` [EXTRACTED]
- [[_month_bounds_datetime()_1]] - `calls` [EXTRACTED]
- [[contribution_service.py]] - `contains` [EXTRACTED]
- [[get_budget_v2()]] - `calls` [INFERRED]
- [[income_for_personal_view()]] - `calls` [EXTRACTED]
- [[test_breakdown_never_reads_fixed_member_real_income()]] - `calls` [INFERRED]
- [[test_caller_relative_for_seed_user()]] - `calls` [INFERRED]
- [[test_caller_sources_keys_match_user_categories()]] - `calls` [INFERRED]
- [[test_other_members_excludes_caller_themselves()]] - `calls` [INFERRED]
- [[test_total_equals_components_sum()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Household_Contributions