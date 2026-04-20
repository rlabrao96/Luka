---
source_file: "backend/tests/test_households.py"
type: "rationale"
community: "Auth & Allocation Services"
location: "L76"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/Auth_&_Allocation_Services
---

# Invariant: each user has AT MOST one active household_members row.     Enforced

## Connections
- [[HouseholdMember]] - `uses` [INFERRED]
- [[test_no_user_has_multiple_active_memberships()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/EXTRACTED #community/Auth_&_Allocation_Services