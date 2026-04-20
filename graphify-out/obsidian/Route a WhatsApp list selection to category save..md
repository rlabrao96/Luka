---
source_file: "backend/modules/whatsapp/handler.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L261"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Route a WhatsApp list selection to category save.

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[WhatsAppSession]] - `uses` [INFERRED]
- [[handle_list_selection()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation