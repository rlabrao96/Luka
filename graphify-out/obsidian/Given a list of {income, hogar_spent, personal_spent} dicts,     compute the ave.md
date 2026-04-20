---
source_file: "backend/modules/budgets/allocation_service.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L21"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Given a list of {income, hogar_spent, personal_spent} dicts,     compute the ave

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[HouseholdBudgetAllocation]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[compute_historical_suggestion()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation