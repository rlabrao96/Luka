---
source_file: "backend/modules/bank_connect/router.py"
type: "rationale"
community: "Luka Connect & Merchant Review"
location: "L82"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Luka_Connect_&_Merchant_Review
---

# Hard delete credentials, auto-created accounts, and their transactions.

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[BankCredential]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[MerchantReviewJob]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[disconnect_bank()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Luka_Connect_&_Merchant_Review