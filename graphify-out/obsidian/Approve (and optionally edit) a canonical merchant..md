---
source_file: "backend/modules/merchant_review/service.py"
type: "rationale"
community: "Luka Connect & Merchant Review"
location: "L205"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Luka_Connect_&_Merchant_Review
---

# Approve (and optionally edit) a canonical merchant.

## Connections
- [[CanonicalMerchant]] - `uses` [INFERRED]
- [[Merchant]] - `uses` [INFERRED]
- [[MerchantReviewJob]] - `uses` [INFERRED]
- [[Notification]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[approve_merchant()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Luka_Connect_&_Merchant_Review