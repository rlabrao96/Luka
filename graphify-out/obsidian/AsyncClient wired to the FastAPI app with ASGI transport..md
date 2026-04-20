---
source_file: "backend/tests/conftest.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L81"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# AsyncClient wired to the FastAPI app with ASGI transport.

## Connections
- [[Household]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[http_client()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation