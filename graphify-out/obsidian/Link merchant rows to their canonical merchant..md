---
source_file: "backend/modules/merchant_review/service.py"
type: "rationale"
community: "Luka Connect & Merchant Review"
location: "L46"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Luka_Connect_&_Merchant_Review
---

# Link merchant rows to their canonical merchant.

## Connections
- [[CanonicalMerchant]] - `uses` [INFERRED]
- [[Merchant]] - `uses` [INFERRED]
- [[MerchantReviewJob]] - `uses` [INFERRED]
- [[Notification]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[_link_merchants_to_canonical()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Luka_Connect_&_Merchant_Review