---
source_file: "backend/modules/bank_connect/accounts.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L1"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Auto-create bank accounts from Luka Connect scrape data and update balances.

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[accounts.py]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation