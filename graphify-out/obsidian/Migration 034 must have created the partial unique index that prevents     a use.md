---
source_file: "backend/tests/test_households.py"
type: "rationale"
community: "Auth & Allocation Services"
location: "L56"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/Auth_&_Allocation_Services
---

# Migration 034 must have created the partial unique index that prevents     a use

## Connections
- [[HouseholdMember]] - `uses` [INFERRED]
- [[test_partial_unique_index_exists()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/EXTRACTED #community/Auth_&_Allocation_Services