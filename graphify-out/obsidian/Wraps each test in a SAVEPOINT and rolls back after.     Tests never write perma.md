---
source_file: "backend/tests/conftest.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L19"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Wraps each test in a SAVEPOINT and rolls back after.     Tests never write perma

## Connections
- [[Household]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[db()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation