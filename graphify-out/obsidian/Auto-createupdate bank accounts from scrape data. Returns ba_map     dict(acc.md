---
source_file: "backend/modules/bank_connect/accounts.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L37"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Auto-create/update bank accounts from scrape data. Returns ba_map:     dict[(acc

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[ensure_accounts()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation