---
source_file: "backend/modules/merchant_review/train_router.py"
type: "rationale"
community: "Luka Connect & Merchant Review"
location: "L1"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Luka_Connect_&_Merchant_Review
---

# Local-only admin router for merchant training UI. Served at /train — no auth req

## Connections
- [[CanonicalMerchant]] - `uses` [INFERRED]
- [[Merchant]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[train_router.py]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Luka_Connect_&_Merchant_Review