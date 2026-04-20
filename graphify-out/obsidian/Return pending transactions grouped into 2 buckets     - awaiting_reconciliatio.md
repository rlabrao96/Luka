---
source_file: "backend/modules/transactions/service.py"
type: "rationale"
community: "Luka Connect & Merchant Review"
location: "L225"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Luka_Connect_&_Merchant_Review
---

# Return pending transactions grouped into 2 buckets:     - awaiting_reconciliatio

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[CanonicalMerchant]] - `uses` [INFERRED]
- [[Merchant]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[get_pending_transactions()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Luka_Connect_&_Merchant_Review