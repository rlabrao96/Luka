---
source_file: "backend/modules/merchants/service.py"
type: "rationale"
community: "Merchants & WhatsApp"
location: "L22"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Merchants_&_WhatsApp
---

# Look up merchant categories: Redis L1 → DB L2 → LLM fallback.     Returns 1 cate

## Connections
- [[Merchant]] - `uses` [INFERRED]
- [[MerchantCategorySelection]] - `uses` [INFERRED]
- [[UserCategoryPreference]] - `uses` [INFERRED]
- [[lookup_merchant()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Merchants_&_WhatsApp