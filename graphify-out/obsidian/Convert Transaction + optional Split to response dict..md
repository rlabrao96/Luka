---
source_file: "backend/modules/transactions/service.py"
type: "rationale"
community: "Luka Connect & Merchant Review"
location: "L351"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Luka_Connect_&_Merchant_Review
---

# Convert Transaction + optional Split to response dict.

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[CanonicalMerchant]] - `uses` [INFERRED]
- [[Merchant]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[_txn_to_dict()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Luka_Connect_&_Merchant_Review