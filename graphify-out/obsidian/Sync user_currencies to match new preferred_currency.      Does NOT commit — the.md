---
source_file: "backend/modules/currencies/service.py"
type: "rationale"
community: "Currencies Module"
location: "L121"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Currencies_Module
---

# Sync user_currencies to match new preferred_currency.      Does NOT commit — the

## Connections
- [[User]] - `uses` [INFERRED]
- [[UserCurrency]] - `uses` [INFERRED]
- [[sync_preferred_currency()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Currencies_Module