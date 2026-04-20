---
source_file: "backend/modules/merchant_review/service.py"
type: "rationale"
community: "Luka Connect & Merchant Review"
location: "L68"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Luka_Connect_&_Merchant_Review
---

# Get all canonical merchants for a review job, with aggregated transaction data.

## Connections
- [[CanonicalMerchant]] - `uses` [INFERRED]
- [[Merchant]] - `uses` [INFERRED]
- [[MerchantReviewJob]] - `uses` [INFERRED]
- [[Notification]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[get_review_cards()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Luka_Connect_&_Merchant_Review