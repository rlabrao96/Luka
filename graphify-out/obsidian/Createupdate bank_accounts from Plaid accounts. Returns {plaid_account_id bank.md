---
source_file: "backend/modules/plaid/sync.py"
type: "rationale"
community: "Plaid & Subscriptions"
location: "L216"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Plaid_&_Subscriptions
---

# Create/update bank_accounts from Plaid accounts. Returns {plaid_account_id: bank

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[PlaidItem]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[ensure_plaid_accounts()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Plaid_&_Subscriptions