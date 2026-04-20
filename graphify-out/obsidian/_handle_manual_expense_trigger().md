---
source_file: "backend/modules/whatsapp/handler.py"
type: "code"
community: "Merchants & WhatsApp"
location: "L325"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Merchants_&_WhatsApp
---

# _handle_manual_expense_trigger()

## Connections
- [[Create a manual transaction from a parsed expense message and start the session.]] - `rationale_for` [EXTRACTED]
- [[Transaction]] - `calls` [INFERRED]
- [[WhatsAppSession]] - `calls` [INFERRED]
- [[_get_user_and_household_by_phone()]] - `calls` [EXTRACTED]
- [[get_user_ranked_categories()]] - `calls` [INFERRED]
- [[handle_text_message()]] - `calls` [EXTRACTED]
- [[handler.py]] - `contains` [EXTRACTED]
- [[parse_manual_expense()]] - `calls` [EXTRACTED]
- [[save_msgid()]] - `calls` [INFERRED]
- [[save_session()]] - `calls` [INFERRED]
- [[send_expense_alert()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Merchants_&_WhatsApp