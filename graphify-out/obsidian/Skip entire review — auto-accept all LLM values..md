---
source_file: "backend/modules/merchant_review/service.py"
type: "rationale"
community: "Luka Connect & Merchant Review"
location: "L285"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Luka_Connect_&_Merchant_Review
---

# Skip entire review — auto-accept all LLM values.

## Connections
- [[CanonicalMerchant]] - `uses` [INFERRED]
- [[Merchant]] - `uses` [INFERRED]
- [[MerchantReviewJob]] - `uses` [INFERRED]
- [[Notification]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[skip_review()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Luka_Connect_&_Merchant_Review