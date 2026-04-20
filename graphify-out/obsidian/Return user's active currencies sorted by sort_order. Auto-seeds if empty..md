---
source_file: "backend/modules/currencies/service.py"
type: "rationale"
community: "Currencies Module"
location: "L14"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Currencies_Module
---

# Return user's active currencies sorted by sort_order. Auto-seeds if empty.

## Connections
- [[User]] - `uses` [INFERRED]
- [[UserCurrency]] - `uses` [INFERRED]
- [[get_currencies()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Currencies_Module