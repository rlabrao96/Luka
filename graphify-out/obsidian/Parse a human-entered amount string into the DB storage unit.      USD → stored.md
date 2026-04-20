---
source_file: "backend/modules/whatsapp/handler.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L30"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Parse a human-entered amount string into the DB storage unit.      USD → stored

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[WhatsAppSession]] - `uses` [INFERRED]
- [[_parse_amount()_1]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation