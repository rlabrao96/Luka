---
source_file: "backend/tests/conftest.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L116"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Override get_db so routes use the mock session.

## Connections
- [[Household]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[override_db()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation