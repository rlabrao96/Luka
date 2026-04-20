---
source_file: "backend/modules/currencies/models.py"
type: "code"
community: "Currencies Module"
location: "L7"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Currencies_Module
---

# UserCurrency

## Connections
- [[Add a currency to the user's active list. Returns new row.]] - `uses` [INFERRED]
- [[Base]] - `uses` [INFERRED]
- [[Base_1]] - `inherits` [EXTRACTED]
- [[Remove a currency. Promotes next if it was primary. Raises if it's the last.]] - `uses` [INFERRED]
- [[Return user's active currencies sorted by sort_order. Auto-seeds if empty.]] - `uses` [INFERRED]
- [[Sync user_currencies to match new preferred_currency.      Does NOT commit — the]] - `uses` [INFERRED]
- [[add_currency()]] - `calls` [INFERRED]
- [[get_currencies()]] - `calls` [INFERRED]
- [[models.py_2]] - `contains` [EXTRACTED]
- [[sync_preferred_currency()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Currencies_Module