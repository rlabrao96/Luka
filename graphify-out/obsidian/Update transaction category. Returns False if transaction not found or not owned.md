---
source_file: "backend/modules/transactions/service.py"
type: "rationale"
community: "Luka Connect & Merchant Review"
location: "L165"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Luka_Connect_&_Merchant_Review
---

# Update transaction category. Returns False if transaction not found or not owned

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[CanonicalMerchant]] - `uses` [INFERRED]
- [[Merchant]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[update_category()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Luka_Connect_&_Merchant_Review