---
source_file: "backend/scripts/test_pipeline.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L1"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Simulate the full transaction pipeline locally against production DB + Redis. Us

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[test_pipeline.py]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation