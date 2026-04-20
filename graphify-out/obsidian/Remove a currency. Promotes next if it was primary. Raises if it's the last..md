---
source_file: "backend/modules/currencies/service.py"
type: "rationale"
community: "Currencies Module"
location: "L84"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Currencies_Module
---

# Remove a currency. Promotes next if it was primary. Raises if it's the last.

## Connections
- [[User]] - `uses` [INFERRED]
- [[UserCurrency]] - `uses` [INFERRED]
- [[delete_currency()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Currencies_Module