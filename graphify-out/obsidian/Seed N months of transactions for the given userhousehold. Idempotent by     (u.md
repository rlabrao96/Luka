---
source_file: "backend/scripts/seed_budget_test_fixtures.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L166"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Seed N months of transactions for the given user/household. Idempotent by     (u

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[CuotaPurchase]] - `uses` [INFERRED]
- [[Household]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[_seed_transactions()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation