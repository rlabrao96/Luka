---
source_file: "backend/modules/bank_connect/router.py"
type: "rationale"
community: "Luka Connect & Merchant Review"
location: "L132"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Luka_Connect_&_Merchant_Review
---

# Trigger a manual sync (async with webhook callback).

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[BankCredential]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[MerchantReviewJob]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[manual_sync()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Luka_Connect_&_Merchant_Review