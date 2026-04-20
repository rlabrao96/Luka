---
source_file: "backend/modules/bank_accounts/router.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L24"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# List bank accounts visible to the current user in this household.      Returns:

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[list_bank_accounts()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation