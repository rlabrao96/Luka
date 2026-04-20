---
source_file: "backend/modules/bank_accounts/router.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L85"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Manually create a bank account for a household.

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[create_bank_account()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation