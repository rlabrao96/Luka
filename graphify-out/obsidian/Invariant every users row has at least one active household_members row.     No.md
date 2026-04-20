---
source_file: "backend/tests/test_households.py"
type: "rationale"
community: "Auth & Allocation Services"
location: "L96"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/Auth_&_Allocation_Services
---

# Invariant: every users row has at least one active household_members row.     No

## Connections
- [[HouseholdMember]] - `uses` [INFERRED]
- [[test_no_orphaned_users()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/EXTRACTED #community/Auth_&_Allocation_Services