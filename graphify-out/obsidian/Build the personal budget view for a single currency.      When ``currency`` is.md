---
source_file: "backend/modules/budgets/personal_service.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L79"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Build the personal budget view for a single currency.      When ``currency`` is

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[Household]] - `uses` [INFERRED]
- [[HouseholdBudgetAllocation]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[get_personal_budget()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation