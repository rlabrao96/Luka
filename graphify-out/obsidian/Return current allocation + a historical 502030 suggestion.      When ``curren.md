---
source_file: "backend/modules/budgets/allocation_service.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L47"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Return current allocation + a historical 50/20/30 suggestion.      When ``curren

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[HouseholdBudgetAllocation]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[get_allocation()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation