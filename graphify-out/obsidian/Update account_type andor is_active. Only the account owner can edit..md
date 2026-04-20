---
source_file: "backend/modules/bank_accounts/router.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L129"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Update account_type and/or is_active. Only the account owner can edit.

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[update_bank_account()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation