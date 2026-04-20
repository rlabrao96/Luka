---
source_file: "backend/scripts/seed_budget_test_fixtures.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L1"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Seed idempotent budget-v2 test fixtures.  Creates 4 test households scoped to @l

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[CuotaPurchase]] - `uses` [INFERRED]
- [[Household]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[seed_budget_test_fixtures.py]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation