---
source_file: "backend/modules/bank_connect/router.py"
type: "rationale"
community: "Luka Connect & Merchant Review"
location: "L62"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Luka_Connect_&_Merchant_Review
---

# Store encrypted credentials and trigger initial full sync (async).     Frontend

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[BankCredential]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[MerchantReviewJob]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[connect_bank()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Luka_Connect_&_Merchant_Review