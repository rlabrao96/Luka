---
source_file: "backend/modules/transactions/service.py"
type: "rationale"
community: "Luka Connect & Merchant Review"
location: "L304"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Luka_Connect_&_Merchant_Review
---

# Two-tier dedup for email transactions:     1. Same amount + SAME bank within 5 m

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[CanonicalMerchant]] - `uses` [INFERRED]
- [[Merchant]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[is_duplicate_transaction()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Luka_Connect_&_Merchant_Review