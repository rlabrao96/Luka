---
source_file: "backend/modules/budgets/v2_service.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L89"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Return (first_day_dt, first_day_next_dt, days_in_month) as UTC datetimes.

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[BudgetV2Response]] - `uses` [INFERRED]
- [[CuotasBlock]] - `uses` [INFERRED]
- [[Household]] - `uses` [INFERRED]
- [[HouseholdBudgetAllocation]] - `uses` [INFERRED]
- [[HouseholdIncomeBreakdown]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[RiskCategory]] - `uses` [INFERRED]
- [[RunwayBlock]] - `uses` [INFERRED]
- [[SankeyBlock]] - `uses` [INFERRED]
- [[SankeyLink]] - `uses` [INFERRED]
- [[SankeyNode]] - `uses` [INFERRED]
- [[SavingsTargetBlock]] - `uses` [INFERRED]
- [[SpendableBlock]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[_month_bounds_datetime()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation