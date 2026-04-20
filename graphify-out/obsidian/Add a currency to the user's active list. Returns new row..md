---
source_file: "backend/modules/currencies/service.py"
type: "rationale"
community: "Currencies Module"
location: "L49"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Currencies_Module
---

# Add a currency to the user's active list. Returns new row.

## Connections
- [[User]] - `uses` [INFERRED]
- [[UserCurrency]] - `uses` [INFERRED]
- [[add_currency()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Currencies_Module