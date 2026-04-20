---
source_file: "backend/modules/transactions/service.py"
type: "rationale"
community: "Luka Connect & Merchant Review"
location: "L191"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Luka_Connect_&_Merchant_Review
---

# Update transaction split type. Returns False if not found or not owned.

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[CanonicalMerchant]] - `uses` [INFERRED]
- [[Merchant]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[update_split_type()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Luka_Connect_&_Merchant_Review