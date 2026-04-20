---
source_file: "backend/modules/whatsapp/session.py"
type: "code"
community: "Merchants & WhatsApp"
location: "L68"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Merchants_&_WhatsApp
---

# get_active_edit_transaction_id()

## Connections
- [[GET()]] - `calls` [INFERRED]
- [[Return the transaction_id currently awaiting a free-text edit reply, or None.]] - `rationale_for` [EXTRACTED]
- [[_active_edit_key()]] - `calls` [EXTRACTED]
- [[handle_text_message()]] - `calls` [INFERRED]
- [[session.py]] - `contains` [EXTRACTED]
- [[test_get_active_edit_returns_none_when_missing()]] - `calls` [INFERRED]
- [[test_save_and_retrieve_active_edit()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Merchants_&_WhatsApp