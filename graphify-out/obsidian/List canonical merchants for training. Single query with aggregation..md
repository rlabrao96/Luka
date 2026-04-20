---
source_file: "backend/modules/merchant_review/train_router.py"
type: "rationale"
community: "Luka Connect & Merchant Review"
location: "L67"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Luka_Connect_&_Merchant_Review
---

# List canonical merchants for training. Single query with aggregation.

## Connections
- [[CanonicalMerchant]] - `uses` [INFERRED]
- [[Merchant]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[list_merchants()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Luka_Connect_&_Merchant_Review