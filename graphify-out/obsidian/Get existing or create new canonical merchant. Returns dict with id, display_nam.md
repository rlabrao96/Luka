---
source_file: "backend/modules/merchant_review/service.py"
type: "rationale"
community: "Luka Connect & Merchant Review"
location: "L20"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Luka_Connect_&_Merchant_Review
---

# Get existing or create new canonical merchant. Returns dict with id, display_nam

## Connections
- [[CanonicalMerchant]] - `uses` [INFERRED]
- [[Merchant]] - `uses` [INFERRED]
- [[MerchantReviewJob]] - `uses` [INFERRED]
- [[Notification]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[_get_or_create_canonical()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Luka_Connect_&_Merchant_Review