---
source_file: "backend/modules/bank_connect/router.py"
type: "rationale"
community: "Luka Connect & Merchant Review"
location: "L283"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Luka_Connect_&_Merchant_Review
---

# Process movements: dedup, reconcile with email txns, create new ones.

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[BankCredential]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[MerchantReviewJob]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[_process_movements()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Luka_Connect_&_Merchant_Review