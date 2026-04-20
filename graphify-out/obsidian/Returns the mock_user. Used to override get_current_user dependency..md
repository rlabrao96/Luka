---
source_file: "backend/tests/conftest.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L88"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Returns the mock_user. Used to override get_current_user dependency.

## Connections
- [[Household]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[mock_current_user()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation