---
source_file: "backend/modules/households/auth.py"
type: "rationale"
community: "Auth & Allocation Services"
location: "L9"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/Auth_&_Allocation_Services
---

# Raise 403 if user is not a member of the household.

## Connections
- [[HouseholdMember]] - `uses` [INFERRED]
- [[require_membership()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/EXTRACTED #community/Auth_&_Allocation_Services