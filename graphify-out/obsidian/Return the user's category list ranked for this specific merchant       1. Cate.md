---
source_file: "backend/modules/merchants/service.py"
type: "rationale"
community: "Merchants & WhatsApp"
location: "L91"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Merchants_&_WhatsApp
---

# Return the user's category list ranked for this specific merchant:       1. Cate

## Connections
- [[Merchant]] - `uses` [INFERRED]
- [[MerchantCategorySelection]] - `uses` [INFERRED]
- [[UserCategoryPreference]] - `uses` [INFERRED]
- [[get_user_ranked_categories()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Merchants_&_WhatsApp