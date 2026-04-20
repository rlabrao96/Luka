---
source_file: "backend/modules/whatsapp/handler.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L395"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Handle a free-text reply during an active edit step, or a new manual expense tri

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[WhatsAppSession]] - `uses` [INFERRED]
- [[handle_text_message()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation