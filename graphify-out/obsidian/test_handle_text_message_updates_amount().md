---
source_file: "backend/tests/test_whatsapp_handler.py"
type: "code"
community: "Merchants & WhatsApp"
location: "L82"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Merchants_&_WhatsApp
---

# test_handle_text_message_updates_amount()

## Connections
- [[When step is awaiting_new_amount, parses int and updates txn.amount.]] - `rationale_for` [EXTRACTED]
- [[_make_redis()]] - `calls` [EXTRACTED]
- [[_session_key()]] - `calls` [INFERRED]
- [[handle_text_message()]] - `calls` [INFERRED]
- [[patch()]] - `calls` [INFERRED]
- [[test_whatsapp_handler.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Merchants_&_WhatsApp