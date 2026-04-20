---
source_file: "backend/modules/merchants/service.py"
type: "rationale"
community: "Merchants & WhatsApp"
location: "L158"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Merchants_&_WhatsApp
---

# Called when a user selects a final category via WhatsApp. Trains the dataset.

## Connections
- [[Merchant]] - `uses` [INFERRED]
- [[MerchantCategorySelection]] - `uses` [INFERRED]
- [[UserCategoryPreference]] - `uses` [INFERRED]
- [[record_category_selection()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Merchants_&_WhatsApp